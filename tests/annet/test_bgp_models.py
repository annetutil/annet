import pytest

from annet.bgp_models import VidCollection, VidRange


@pytest.mark.parametrize(
    ["raw", "ranges", "vids"],
    [
        (
            "1",
            [VidRange(1, 1)],
            [1],
        ),
        (
            "1, 2",
            [VidRange(1, 1), VidRange(2, 2)],
            [1, 2],
        ),
        (
            "1-4",
            [VidRange(1, 4)],
            [1, 2, 3, 4],
        ),
        (
            "1-4,10, 20-22",
            [VidRange(1, 4), VidRange(10, 10), VidRange(20, 22)],
            [1, 2, 3, 4, 10, 20, 21, 22],
        ),
    ],
)
def test_parse_vid_range(raw, ranges, vids):
    collection = VidCollection.parse(raw)
    assert collection == VidCollection(ranges)
    assert str(collection) == raw.replace(" ", "")
    assert list(collection) == vids
