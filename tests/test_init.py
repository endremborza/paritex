import paritex


def test_import():
    assert isinstance(paritex.__version__, str)


def test_layout_contract():
    assert paritex.REFS_BIB == "refs.bib"
    assert paritex.MAIN_TEX == "main.tex"
    assert {paritex.ORIGINAL, paritex.REBUILT, paritex.ASSETS, paritex.REPORT} == {
        "original.pdf",
        "main.pdf",
        "assets",
        "report.json",
    }
