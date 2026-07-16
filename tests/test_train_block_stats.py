from bot.train_block_stats import MAX_SPOT_BATTLES, block_pattern_from_cells, block_pattern_from_slots


def test_max_spot_battles_threshold():
    assert MAX_SPOT_BATTLES == 10_000_000


def test_single_row_segments():
    assert block_pattern_from_cells([(0, 0), (0, 1), (0, 2), (0, 4)]) == "3x1 + 1x1"


def test_two_row_rectangle():
    assert block_pattern_from_slots([1, 2, 3, 11, 12, 13]) == "3x2"


def test_four_wide_row():
    assert block_pattern_from_cells([(0, 1), (0, 2), (0, 3), (0, 4)]) == "4x1"


def test_horizontal_plus_vertical():
    assert block_pattern_from_cells([(0, 1), (0, 2), (0, 3), (1, 2)]) == "3x1 + 1x1"


def test_reported_train_shape_keeps_horizontal_block():
    assert block_pattern_from_slots([1, 2, 3, 12]) == "3x1 + 1x1"
