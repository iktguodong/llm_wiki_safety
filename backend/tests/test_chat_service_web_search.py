from backend.services.chat import ChatService


def _make_result(title: str, snippet: str) -> dict[str, str]:
    return {
        "title": title,
        "url": f"https://example.com/{title}",
        "snippet": snippet,
    }


def test_web_result_selection_scales_with_question_complexity():
    results = [
        _make_result("应急预案指南", "应急预案的编制、执行与检查要求。"),
        _make_result("培训要求清单", "培训要求和考核标准说明。"),
        _make_result("检查清单", "检查清单与复盘要点。"),
        _make_result("事故案例汇总", "事故案例分析与复盘。"),
        _make_result("适用场景说明", "适用场景和边界条件。"),
        _make_result("无关内容", "与问题无关的内容。"),
    ]

    simple = ChatService._select_web_results("应急预案是什么", results)
    complex_results = ChatService._select_web_results(
        "请对比应急预案、培训要求、检查清单和事故案例的区别、优缺点、适用场景，并分别列出要求和案例。",
        results,
    )

    assert len(simple) == 3
    assert len(complex_results) == 6
    assert simple[0]["title"] == "应急预案指南"
    assert complex_results[0]["title"] == "应急预案指南"


def test_web_result_format_keeps_continuous_numbering():
    results = [
        _make_result("应急预案指南", "应急预案的编制、执行与检查要求。"),
        _make_result("培训要求清单", "培训要求和考核标准说明。"),
        _make_result("检查清单", "检查清单与复盘要点。"),
    ]

    formatted = ChatService._format_web_results(results)

    assert "### 结果1:" in formatted
    assert "### 结果2:" in formatted
    assert "### 结果3:" in formatted
