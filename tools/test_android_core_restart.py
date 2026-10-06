"""Device regression harness. Uses only the separate .verification application and fake bots."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time
import zipfile

PACKAGE = 'com.tsbot.android.verification'
ROOT = Path(__file__).resolve().parents[1]


def fixture(label, broken=False):
    client = textwrap.dedent(f'''
        import json, os, threading, time
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[4]
        LABEL = {label!r}
        {'raise RuntimeError("probe import failure")' if broken else ''}
        (ROOT / 'probe_loaded').write_text(json.dumps(dict(label=LABEL, pid=os.getpid())))
        def _cache_flush(force=False):
            pass
        def background_cache():
            while True:
                time.sleep(1)
        threading.Thread(target=background_cache, daemon=True, name='probe-old-cache').start()
    ''')
    coordinator = textwrap.dedent('''
        import json, os, threading, time
        from .client import ROOT, LABEL
        account_threads = {}
        account_stops = {}
        _party_engines = {}
        parties = {}
        def state():
            (ROOT/'probe_state').write_text(json.dumps(dict(label=LABEL, pid=os.getpid(),
                active=sorted(u for u,t in account_threads.items() if t.is_alive()))))
        def setup_party_runtime(pidx, mode, ip, server_id, flat, *args):
            parties[pidx] = flat.split(chr(1))[::5]
        def start_party(pidx):
            for user in parties.get(pidx, []):
                stop = threading.Event()
                account_stops[user] = stop
                thread = threading.Thread(target=stop.wait, daemon=True)
                account_threads[user] = thread
                thread.start()
            state()
        def stop_account(user, **kw):
            if user in account_stops: account_stops[user].set()
            if user in account_threads: account_threads[user].join(1)
            state()
        def stop_all(**kw):
            for user in list(account_threads): stop_account(user)
            time.sleep(1)
        def stop_party(pidx):
            for user in parties.get(pidx, []): stop_account(user)
        def is_account_running(user):
            return user in account_threads and account_threads[user].is_alive()
        def account_status(user):
            return dict(running=is_account_running(user), char=user)
        def get_account_log(*args):
            return 'verification fake bot'
        state()
    ''')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, source in {'__init__.py': '', 'client.py': client,
                             'run_party_digioi.py': coordinator, 'config.py': ''}.items():
            z.writestr('android/train_bot/' + name, source)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()

    def adb(*parts, data=None, check=True):
        result = subprocess.run([args.adb, '-s', args.serial, *parts], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace') + result.stdout.decode(errors='replace'))
        return result.stdout.decode(errors='replace').strip() if result.returncode == 0 else ''

    def read(name):
        value = adb('shell', 'run-as', PACKAGE, 'cat', 'files/' + name, check=False)
        return json.loads(value) if value else None

    def upload_bundle(data):
        with tempfile.TemporaryDirectory(prefix='ats-core-probe-') as directory:
            bundle = Path(directory) / 'probe.zip'
            bundle.write_bytes(data)
            remote = '/data/local/tmp/ats-verification-probe.zip'
            adb('push', str(bundle), remote)
            adb('shell', 'chmod', '644', remote)
            adb('shell', 'run-as', PACKAGE, 'cp', remote, 'files/probe.zip')
            adb('shell', 'rm', remote)

    def wait(predicate, label, timeout=100):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            error = adb('shell', 'run-as', PACKAGE, 'cat', 'files/probe_error', check=False)
            if error: raise AssertionError(error)
            try:
                if predicate():
                    print('PASS:', label, flush=True)
                    return
            except (ValueError, TypeError, KeyError):
                pass
            time.sleep(1)
        raise AssertionError('Timed out: ' + label)

    def launch(phase, *extras):
        adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/com.tsbot.android.CoreUpdateProbeActivity',
            '--es', 'phase', phase, *extras)

    def install_core(label, version, broken=False, cancel=False):
        adb('shell', 'run-as', PACKAGE, 'mkdir', '-p', 'files')
        upload_bundle(fixture(label, broken))
        launch('update', '--es', 'version', version, '--ez', 'cancel', str(cancel).lower())

    output = ROOT/'android/app/build/outputs/apk'
    debug = json.loads((output/'debug/output-metadata.json').read_text())
    assert debug['applicationId'] == PACKAGE
    adb('install', '-r', str(output/'debug'/debug['elements'][0]['outputFile']))
    adb('install', '-r', str(output/'androidTest/debug/app-debug-androidTest.apk'))
    tests = adb('shell', 'am', 'instrument', '-w', '-e', 'class',
        'com.tsbot.android.CoreUpdateRestartTest', PACKAGE+'.test/androidx.test.runner.AndroidJUnitRunner')
    print(tests, flush=True)
    assert 'OK (' in tests and 'FAILURES' not in tests
    assert adb('shell', 'pm', 'clear', PACKAGE) == 'Success'

    install_core('baseline', '9.1.1.202610060001')
    wait(lambda: read('probe_loaded')['label'] == 'baseline' and not read('core_update_restart.json'),
         'baseline activates in a fresh process')
    launch('start')
    wait(lambda: read('probe_state')['active'] == ['probe-active', 'probe-stopped'], 'two fake accounts start')
    launch('stop-one')
    wait(lambda: read('probe_state')['active'] == ['probe-active'], 'manual stop remains stopped')
    previous_pid = read('probe_loaded')['pid']
    install_core('updated', '9.1.1.202610060002')
    wait(lambda: read('probe_state')['label'] == 'updated' and
         read('probe_state')['active'] == ['probe-active'] and read('probe_loaded')['pid'] != previous_pid,
         'update replaces process and resumes only active account')

    previous_pid = read('probe_loaded')['pid']
    install_core('broken', '9.1.1.202610060003', broken=True)
    wait(lambda: read('probe_loaded')['pid'] != previous_pid and read('probe_state')['label'] == 'updated' and
         read('probe_state')['active'] == ['probe-active'] and not read('core_update_restart.json'),
         'failed import rolls back and resumes old core')

    install_core('cancelled', '9.1.1.202610060004', cancel=True)
    wait(lambda: read('probe_state')['label'] == 'cancelled' and read('probe_state')['active'] == [] and
         not read('core_update_restart.json'), 'Stop All during update prevents automatic restart of accounts')
    upload_bundle((ROOT/'aTSBot-bundle.zip').read_bytes())
    real_version = '9.' + json.loads((ROOT/'aTSBot/version.json').read_text(encoding='utf-8'))['version']
    previous_pid = adb('shell', 'pidof', PACKAGE, check=False)
    launch('update', '--es', 'version', real_version, '--ez', 'show_ui', 'true')
    # No journal exists before the update starts either, so the process must also have been replaced.
    wait(lambda: adb('shell', 'pidof', PACKAGE, check=False) not in ('', previous_pid) and
         not read('core_update_restart.json') and
         adb('shell', 'run-as', PACKAGE, 'cat', 'files/bot_bundle/version.txt', check=False) == real_version,
         'real bundled core activates')
    adb('shell', 'run-as', PACKAGE, 'rm', '-f', 'files/probe_report')
    launch('report')
    wait(lambda: read('probe_report')['loaded'] == real_version, 'real core loaded version is confirmed')
    print('ALL DEVICE CORE-UPDATE CHECKS PASSED (verification app only)', flush=True)


if __name__ == '__main__':
    main()
