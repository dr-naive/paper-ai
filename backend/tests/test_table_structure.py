from app.services.table_structure import (
    build_table_cells,
    merge_cross_page_tables,
    normalize_table_structure,
)


def test_normalizes_multi_row_headers_and_semantic_rows():
    table = {
        "page": 3,
        "caption": "表1 实验结果（单位：%）",
        "content": [
            ["方法", "测试集", "测试集"],
            ["", "准确率", "召回率"],
            ["A", "91.2", "88.5"],
            ["注：数值越大越好", "", ""],
        ],
        "cell_bboxes": [[[0, 0, 1, 1]] * 3] * 4,
    }
    result = normalize_table_structure(table, 1)
    assert result["header_rows"] == [0, 1]
    assert result["header_tree"][1] == ["测试集", "准确率"]
    assert "测试集 / 准确率=91.2" in result["row_records"][0]["text"]
    assert result["footnotes"] == ["注：数值越大越好"]
    assert "%" in result["units"]
    cells = build_table_cells(table, result)
    assert cells[4]["is_header"] is True
    assert cells[7]["bbox"] == [0, 0, 1, 1]


def test_merges_adjacent_continued_table_and_drops_repeated_header():
    tables = [
        {"page": 4, "caption": "表2 消融实验", "content": [["方法", "F1"], ["A", "80"]]},
        {"page": 5, "caption": "续表2 消融实验", "content": [["方法", "F1"], ["B", "82"]]},
    ]
    merged = merge_cross_page_tables(tables)
    assert len(merged) == 1
    assert merged[0]["pages"] == [4, 5]
    assert merged[0]["content"] == [["方法", "F1"], ["A", "80"], ["B", "82"]]
    assert merged[0]["_row_pages"] == [4, 4, 5]


def test_normalizes_vlm_markdown_when_raw_cells_are_missing():
    result = normalize_table_structure({
        "page": 7,
        "caption": "Table 3",
        "content": [],
        "markdown_content": "| Method | F1 |\n|---|---|\n| A | 83.2 |",
    }, 3)
    assert result["grid"] == [["Method", "F1"], ["A", "83.2"]]
    assert result["row_records"][0]["fields"][1]["value"] == "83.2"
