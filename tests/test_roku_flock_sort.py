"""Poster-grid tag and flock sort rules for Roku VoD 1.0.55.

These match ``posterGridTag``, ``sortFlock``, and ``flockSortBefore`` in
``roku-channel/components/JellyfinTask.brs``. The channel cannot run here;
this module is the executable copy of that order.
"""

from __future__ import annotations


def poster_grid_tag(
    generation: str = "",
    pedigree: str = "",
    sheep_id: str = "",
    filename: str = "",
    media_path: str = "",
) -> str:
    blob = f"{filename} {media_path}".lower()
    gen = (generation or "").lower()
    if ".tuple." in blob or "/tuple/" in blob or "\\tuple\\" in blob or gen == "tuple":
        return "tuple"
    if ".pedigree." in blob or "/pedigree/" in blob or "\\pedigree\\" in blob or gen == "pedigree":
        return "breed"
    sheep = (sheep_id or "").lower()
    ped = (pedigree or "").lower()
    if sheep in {"mutate", "cross", "blend", "interpolate"}:
        return "breed"
    if any(word in ped for word in ("mutate", "cross", "blend", "interpolate")):
        return "breed"
    if gen.isdigit():
        return f"gen {generation}"
    return ""


def meta_line(duration: str, tag: str, license_name: str) -> str:
    bits = [bit for bit in (duration, tag, license_name) if bit]
    return " · ".join(bits)


def _filename_key(item: dict) -> str:
    name = str(item.get("filename") or "").strip().lower()
    if name in ("", "untitled"):
        return "~"
    return name


def _alias_key(item: dict) -> str:
    alias = str(item.get("alias") or "").strip().lower()
    if alias:
        return alias
    return _filename_key(item)


def _license_key(item: dict) -> str:
    lic = str(item.get("license") or "").strip().lower()
    return lic or "~"


def _generation_rank(item: dict) -> int:
    tag = item.get("gridTag") or ""
    if tag == "breed":
        return 1
    if tag == "tuple":
        return 2
    gen = str(item.get("generation") or "")
    if gen.isdigit():
        return 0
    return 3


def _sort_key(item: dict, mode: str) -> tuple:
    if mode == "alias":
        return (_alias_key(item),)
    if mode == "duration":
        return (int(item.get("length") or 0), _filename_key(item))
    if mode == "license":
        return (_license_key(item), _filename_key(item))
    if mode == "generation":
        rank = _generation_rank(item)
        if rank == 0:
            sheep = str(item.get("sheepId") or "")
            sheep_n = int(sheep) if sheep.isdigit() else 0
            return (0, int(item.get("generation") or 0), sheep_n, _filename_key(item))
        return (rank, 0, 0, _filename_key(item))
    return (_filename_key(item),)


def sort_flock(items: list[dict], mode: str) -> list[dict]:
    if mode == "folder":
        return list(items)
    if mode not in {"filename", "alias", "generation", "duration", "license"}:
        mode = "filename"
    return sorted(items, key=lambda item: _sort_key(item, mode))


def apply_cap(items: list[dict], mode: str, cap: int) -> list[dict]:
    ordered = sort_flock(items, mode)
    if mode == "folder":
        return ordered
    return ordered[:cap]


def _sheep(**kwargs) -> dict:
    item = {
        "filename": "",
        "alias": "",
        "generation": "",
        "sheepId": "",
        "pedigree": "",
        "license": "",
        "length": 0,
        "mediaPath": "",
    }
    item.update(kwargs)
    item["gridTag"] = poster_grid_tag(
        item["generation"],
        item["pedigree"],
        item["sheepId"],
        item["filename"],
        item["mediaPath"],
    )
    return item


def test_poster_tags_number_breed_and_tuple():
    archive = _sheep(filename="electricsheep.247.00600", generation="247", sheepId="00600")
    mutate = _sheep(
        filename="electricsheep.pedigree.mutate.aa",
        generation="pedigree",
        sheepId="mutate",
        mediaPath="/media/sheep/by-generation/pedigree/electricsheep.pedigree.mutate.aa.mp4",
    )
    cross = _sheep(filename="electricsheep.pedigree.cross.bb", generation="pedigree", sheepId="cross")
    blend = _sheep(filename="electricsheep.pedigree.blend.cc", generation="pedigree", sheepId="blend")
    interp = _sheep(
        filename="electricsheep.pedigree.interpolate.dd",
        generation="pedigree",
        sheepId="interpolate",
    )
    tuple_item = _sheep(
        filename="electricsheep.tuple.247.00600_to_245.00061",
        generation="tuple",
        mediaPath="/media/sheep/by-generation/tuple/electricsheep.tuple.247.00600_to_245.00061.mp4",
    )
    misc = _sheep(filename="electricsheep.misc.note", generation="misc")
    human = _sheep(filename="electricsheep.242.00483", generation="242", sheepId="00483", pedigree="human")

    assert archive["gridTag"] == "gen 247"
    assert mutate["gridTag"] == "breed"
    assert cross["gridTag"] == "breed"
    assert blend["gridTag"] == "breed"
    assert interp["gridTag"] == "breed"
    assert tuple_item["gridTag"] == "tuple"
    assert misc["gridTag"] == ""
    assert human["gridTag"] == "gen 242"
    assert meta_line("39s", tuple_item["gridTag"], "cc-by") == "39s · tuple · cc-by"
    assert meta_line("23s", mutate["gridTag"], "cc-by-nc") == "23s · breed · cc-by-nc"


def test_filename_is_the_default_order():
    items = [
        _sheep(filename="electricsheep.247.18817"),
        _sheep(filename="electricsheep.165.06790"),
        _sheep(filename="electricsheep.pedigree.mutate.aa"),
        _sheep(filename="Untitled"),
    ]
    names = [item["filename"] for item in sort_flock(items, "filename")]
    assert names == [
        "electricsheep.165.06790",
        "electricsheep.247.18817",
        "electricsheep.pedigree.mutate.aa",
        "Untitled",
    ]
    assert [item["filename"] for item in sort_flock(items, "")] == names
    assert [item["filename"] for item in sort_flock(items, "nope")] == names


def test_alias_sort_falls_back_to_filename():
    items = [
        _sheep(filename="electricsheep.247.00010", alias=""),
        _sheep(filename="electricsheep.245.00061", alias="frosty_swirles"),
        _sheep(filename="electricsheep.242.00483", alias="angry_bardeen"),
    ]
    ordered = [item["alias"] or item["filename"] for item in sort_flock(items, "alias")]
    assert ordered == [
        "angry_bardeen",
        "electricsheep.247.00010",
        "frosty_swirles",
    ]


def test_generation_sort_is_numeric_then_breed_then_tuple():
    items = [
        _sheep(filename="electricsheep.tuple.a_to_b", generation="tuple"),
        _sheep(filename="electricsheep.247.00010", generation="247", sheepId="00010"),
        _sheep(filename="electricsheep.pedigree.cross.bb", generation="pedigree", sheepId="cross"),
        _sheep(filename="electricsheep.165.06790", generation="165", sheepId="06790"),
        _sheep(filename="electricsheep.247.00002", generation="247", sheepId="2"),
        _sheep(filename="electricsheep.pedigree.mutate.aa", generation="pedigree", sheepId="mutate"),
        _sheep(filename="note", generation="misc"),
    ]
    names = [item["filename"] for item in sort_flock(items, "generation")]
    assert names == [
        "electricsheep.165.06790",
        "electricsheep.247.00002",
        "electricsheep.247.00010",
        "electricsheep.pedigree.cross.bb",
        "electricsheep.pedigree.mutate.aa",
        "electricsheep.tuple.a_to_b",
        "note",
    ]


def test_duration_and_license_use_filename_as_the_tiebreak():
    items = [
        _sheep(filename="electricsheep.247.00020", length=39, license="cc-by-nc"),
        _sheep(filename="electricsheep.247.00010", length=13, license="cc-by"),
        _sheep(filename="electricsheep.247.00030", length=13, license=""),
        _sheep(filename="electricsheep.247.00005", length=39, license="cc-by"),
    ]
    by_len = [item["filename"] for item in sort_flock(items, "duration")]
    assert by_len == [
        "electricsheep.247.00010",
        "electricsheep.247.00030",
        "electricsheep.247.00005",
        "electricsheep.247.00020",
    ]
    by_lic = [item["filename"] for item in sort_flock(items, "license")]
    assert by_lic == [
        "electricsheep.247.00005",
        "electricsheep.247.00010",
        "electricsheep.247.00020",
        "electricsheep.247.00030",
    ]


def test_equal_keys_keep_input_order_and_folder_keeps_the_walk():
    first = _sheep(filename="electricsheep.247.00010", alias="same_name")
    second = _sheep(filename="electricsheep.245.00061", alias="same_name")
    ordered = sort_flock([first, second], "alias")
    assert ordered[0]["filename"] == "electricsheep.247.00010"
    assert ordered[1]["filename"] == "electricsheep.245.00061"
    walked = [
        _sheep(filename="electricsheep.247.18817"),
        _sheep(filename="electricsheep.165.06790"),
    ]
    assert [item["filename"] for item in sort_flock(walked, "folder")] == [
        "electricsheep.247.18817",
        "electricsheep.165.06790",
    ]


def test_sorted_modes_keep_the_first_rows_when_over_the_cap():
    items = [
        _sheep(filename="electricsheep.247.00030"),
        _sheep(filename="electricsheep.165.00010"),
        _sheep(filename="electricsheep.242.00020"),
    ]
    kept = [item["filename"] for item in apply_cap(items, "filename", 2)]
    assert kept == ["electricsheep.165.00010", "electricsheep.242.00020"]
    # folder stays in walk order. The channel still random-prunes that walk
    # above 313; this helper only checks it does not take a sorted prefix.
    folder = [item["filename"] for item in sort_flock(items, "folder")]
    assert folder == [
        "electricsheep.247.00030",
        "electricsheep.165.00010",
        "electricsheep.242.00020",
    ]
