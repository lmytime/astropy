import numpy as np
import pytest

from astropy.io import ascii
from astropy.io.ascii.qdp import _get_lines_from_file, _read_table_qdp, _write_table_qdp
from astropy.table import Column, MaskedColumn, Table
from astropy.utils.exceptions import AstropyUserWarning


def test_get_tables_from_qdp_file(tmp_path):
    example_qdp = """
    ! Swift/XRT hardness ratio of trigger: XXXX, name: BUBU X-2
    ! Columns are as labelled
    READ TERR 1
    READ SERR 2
    ! WT -- hard data
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   -0.212439       0.212439
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   0.000000        0.000000
    NO NO NO NO NO
    ! WT -- soft data
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   0.726155        0.583890
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   2.410935        1.393592
    NO NO NO NO NO
    ! WT -- hardness ratio
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   -0.292553       -0.374935
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   0.000000        -nan
    """

    path = tmp_path / "test.qdp"

    with open(path, "w") as fp:
        print(example_qdp, file=fp)

    table0 = _read_table_qdp(fp.name, names=["MJD", "Rate"], table_id=0)
    assert table0.meta["initial_comments"][0].startswith("Swift")
    assert table0.meta["comments"][0].startswith("WT -- hard data")
    table2 = _read_table_qdp(fp.name, names=["MJD", "Rate"], table_id=2)
    assert table2.meta["initial_comments"][0].startswith("Swift")
    assert table2.meta["comments"][0].startswith("WT -- hardness")
    assert np.isclose(table2["MJD_nerr"][0], -2.37847222222222e-05)


def lowercase_header(value):
    """Make every non-comment line lower case."""
    lines = []
    for line in value.splitlines():
        if not line.startswith("!"):
            line = line.lower()
        lines.append(line)
    return "\n".join(lines)


@pytest.mark.parametrize("lowercase", [False, True])
def test_roundtrip(tmp_path, lowercase):
    example_qdp = """
    ! Swift/XRT hardness ratio of trigger: XXXX, name: BUBU X-2
    ! Columns are as labelled
    READ TERR 1
    READ SERR 2
    ! WT -- hard data
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   NO       0.212439
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   0.000000        0.000000
    NO NO NO NO NO
    ! WT -- soft data
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   0.726155        0.583890
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   2.410935        1.393592
    NO NO NO NO NO
    ! WT -- hardness ratio
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   -0.292553       -0.374935
    55045.099887 1.14467592592593e-05    -1.14467592592593e-05   0.000000        NO
    ! Add command, just to raise the warning.
    READ TERR 1
    ! WT -- whatever
    !MJD            Err (pos)       Err(neg)        Rate            Error
    53000.123456 2.37847222222222e-05    -2.37847222222222e-05   -0.292553       -0.374935
    NO 1.14467592592593e-05    -1.14467592592593e-05   0.000000        NO
    """
    if lowercase:
        example_qdp = lowercase_header(example_qdp)

    path = str(tmp_path / "test.qdp")
    path2 = str(tmp_path / "test2.qdp")

    with open(path, "w") as fp:
        print(example_qdp, file=fp)
    with pytest.warns(AstropyUserWarning) as record:
        table = _read_table_qdp(path, names=["MJD", "Rate"], table_id=0)
    assert np.any(
        [
            "This file contains multiple command blocks" in r.message.args[0]
            for r in record
        ]
    )

    _write_table_qdp(table, path2)

    new_table = _read_table_qdp(path2, names=["MJD", "Rate"], table_id=0)

    for col in new_table.colnames:
        is_masked = np.array([np.ma.is_masked(val) for val in new_table[col]])
        if np.any(is_masked):
            # All NaN values are read as such.
            assert np.ma.is_masked(table[col][is_masked])

        is_nan = np.array(
            [(not np.ma.is_masked(val) and np.isnan(val)) for val in new_table[col]]
        )
        # All non-NaN values are the same
        assert np.allclose(new_table[col][~is_nan], table[col][~is_nan])
        if np.any(is_nan):
            # All NaN values are read as such.
            assert np.isnan(table[col][is_nan])
    assert np.allclose(new_table["MJD_perr"], [2.378472e-05, 1.1446759e-05])

    for meta_name in ["initial_comments", "comments"]:
        assert meta_name in new_table.meta


def test_read_example():
    example_qdp = """
        ! Initial comment line 1
        ! Initial comment line 2
        READ TERR 1
        READ SERR 3
        ! Table 0 comment
        !a a(pos) a(neg) b c ce d
        53000.5   0.25  -0.5   1  1.5  3.5 2
        54000.5   1.25  -1.5   2  2.5  4.5 3
        NO NO NO NO NO
        ! Table 1 comment
        !a a(pos) a(neg) b c ce d
        54000.5   2.25  -2.5   NO  3.5  5.5 5
        55000.5   3.25  -3.5   4  4.5  6.5 nan
        """
    dat = ascii.read(example_qdp, format="qdp", table_id=1, names=["a", "b", "c", "d"])
    t = Table.read(
        example_qdp, format="ascii.qdp", table_id=1, names=["a", "b", "c", "d"]
    )

    assert np.allclose(t["a"], [54000, 55000])
    assert t["c_err"][0] == 5.5
    assert np.ma.is_masked(t["b"][0])
    assert np.isnan(t["d"][1])

    for col1, col2 in zip(t.itercols(), dat.itercols()):
        assert np.allclose(col1, col2, equal_nan=True)


def test_roundtrip_example(tmp_path):
    example_qdp = """
        ! Initial comment line 1
        ! Initial comment line 2
        READ TERR 1
        READ SERR 3
        ! Table 0 comment
        !a a(pos) a(neg) b c ce d
        53000.5   0.25  -0.5   1  1.5  3.5 2
        54000.5   1.25  -1.5   2  2.5  4.5 3
        NO NO NO NO NO
        ! Table 1 comment
        !a a(pos) a(neg) b c ce d
        54000.5   2.25  -2.5   NO  3.5  5.5 5
        55000.5   3.25  -3.5   4  4.5  6.5 nan
        """
    test_file = tmp_path / "test.qdp"

    t = Table.read(
        example_qdp, format="ascii.qdp", table_id=1, names=["a", "b", "c", "d"]
    )
    t.write(test_file, err_specs={"terr": [1], "serr": [3]})
    t2 = Table.read(test_file, names=["a", "b", "c", "d"], table_id=0)

    for col1, col2 in zip(t.itercols(), t2.itercols()):
        assert np.allclose(col1, col2, equal_nan=True)


def test_roundtrip_example_comma(tmp_path):
    example_qdp = """
        ! Initial comment line 1
        ! Initial comment line 2
        READ TERR 1
        READ SERR 3
        ! Table 0 comment
        !a,a(pos),a(neg),b,c,ce,d
        53000.5,0.25,-0.5,1,1.5,3.5,2
        54000.5,1.25,-1.5,2,2.5,4.5,3
        NO,NO,NO,NO,NO
        ! Table 1 comment
        !a,a(pos),a(neg),b,c,ce,d
        54000.5,2.25,-2.5,NO,3.5,5.5,5
        55000.5,3.25,-3.5,4,4.5,6.5,nan
        """
    test_file = tmp_path / "test.qdp"

    t = Table.read(
        example_qdp, format="ascii.qdp", table_id=1, names=["a", "b", "c", "d"], sep=","
    )
    t.write(test_file, err_specs={"terr": [1], "serr": [3]})
    t2 = Table.read(test_file, names=["a", "b", "c", "d"], table_id=0)

    # t.values_equal(t2)
    for col1, col2 in zip(t.itercols(), t2.itercols()):
        assert np.allclose(col1, col2, equal_nan=True)


def test_read_write_simple(tmp_path):
    test_file = tmp_path / "test.qdp"
    t1 = Table()
    t1.add_column(Column(name="a", data=[1, 2, 3, 4]))
    t1.add_column(
        MaskedColumn(
            data=[4.0, np.nan, 3.0, 1.0], name="b", mask=[False, False, False, True]
        )
    )
    t1.write(test_file, format="ascii.qdp")
    with pytest.warns(UserWarning) as record:
        t2 = Table.read(test_file, format="ascii.qdp")
    assert np.any(
        [
            "table_id not specified. Reading the first available table"
            in r.message.args[0]
            for r in record
        ]
    )

    assert np.allclose(t2["col1"], t1["a"])
    assert np.all(t2["col1"] == t1["a"])

    good = ~np.isnan(t1["b"])
    assert np.allclose(t2["col2"][good], t1["b"][good])


def test_read_write_simple_specify_name(tmp_path):
    test_file = tmp_path / "test.qdp"
    t1 = Table()
    t1.add_column(Column(name="a", data=[1, 2, 3]))
    # Give a non-None err_specs
    t1.write(test_file, format="ascii.qdp")
    t2 = Table.read(test_file, table_id=0, format="ascii.qdp", names=["a"])
    assert np.all(t2["a"] == t1["a"])


def test_get_lines_from_qdp(tmp_path):
    test_file = str(tmp_path / "test.qdp")
    text_string = "A\nB"
    text_output = _get_lines_from_file(text_string)
    with open(test_file, "w") as fobj:
        print(text_string, file=fobj)
    file_output = _get_lines_from_file(test_file)
    list_output = _get_lines_from_file(["A", "B"])
    for i, line in enumerate(["A", "B"]):
        assert file_output[i] == line
        assert list_output[i] == line
        assert text_output[i] == line


@pytest.mark.parametrize("spacelike", ["", " ", "   ", "\t", "\v", "\r", "\n", "\f"])
def test_read_qdpfile_with_oneNO_start_new_sector(tmp_path, spacelike):
    example_qdp = f"""
READ Terr 1 2
9.0150001E+00  1.5000167E-02 -1.5000167E-02 -2.7721735E-03  5.7468953E-02 -5.7468953E-02  8.2039691E-02  7.8058078E-02
9.0500002E+00  1.9999990E-02 -1.9999990E-02  1.1883142E-01  7.9723340E-02 -7.9723340E-02  8.3517993E-02  8.5578051E-02
{spacelike}NO
1.9920001E+01  2.9999205E-02 -2.9999205E-02  2.1270609E-01  8.9663795E-02 -8.9663795E-02  9.9843595E-02  1.4176735E-01
1.9975000E+01  2.5000445E-02 -2.5000445E-02  1.1424498E-01  8.8841605E-02 -8.8841605E-02  1.2776274E-01  1.6331280E-01
"""

    path = tmp_path / "test.qdp"

    with open(path, "w") as fp:
        fp.write(example_qdp)

    table0 = Table.read(
        path, format="ascii.qdp", names=["x", "y", "mod", "bkg"], table_id=0
    )
    assert np.allclose(table0["x"], [9.0150001, 9.0500002])
    assert np.allclose(table0["y"], [-0.0027721735, 0.11883142])
    table1 = Table.read(
        path, format="ascii.qdp", names=["x", "y", "mod", "bkg"], table_id=1
    )
    assert np.allclose(table1["x"], [19.920001, 19.975])
    assert np.allclose(table1["y"], [0.21270609, 0.11424498])
