from app.services.ingest import chunk_text, extract_html, markdown_to_text


def test_chunk_text_splits_long_content():
    text = "知识库 " * 400
    parts = chunk_text(text, size=80, overlap=10)
    assert len(parts) > 3
    assert all(parts)


def test_markdown_to_text_strips_markup():
    text = markdown_to_text("# 标题\n\n这是 [链接](https://example.com) 与 `代码`")
    assert "标题" in text
    assert "链接" in text
    assert "https://" not in text


def test_extract_html_drops_script():
    html = "<html><script>alert(1)</script><p>发布流程</p></html>"
    assert "发布流程" in extract_html(html)
    assert "alert" not in extract_html(html)
