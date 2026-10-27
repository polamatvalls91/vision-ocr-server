from vision_ocr_server.lines import to_lines


def box(x, y, h=0.01):
    """Vision's normalised (x, y, w, h), origin bottom-left."""
    return (x, y, 0.1, h)


def test_words_on_one_line_read_left_to_right():
    assert to_lines([("TOTAL", 1.0, box(0.8, 0.10)), ("AMOUNT", 1.0, box(0.1, 0.10))]) == "AMOUNT TOTAL"


def test_lines_read_top_to_bottom():
    observations = [("138,47", 1.0, box(0.8, 0.05)), ("INVOICE 16645", 1.0, box(0.1, 0.90))]
    assert to_lines(observations) == "INVOICE 16645\n138,47"


def test_a_slightly_lower_word_stays_on_its_line():
    observations = [("68,75", 1.0, box(0.3, 0.200)), ("10,0 %", 1.0, box(0.5, 0.196)), ("6,88", 1.0, box(0.6, 0.203))]
    assert to_lines(observations) == "68,75 10,0 % 6,88"


def test_nothing_read():
    assert to_lines([]) == ""
