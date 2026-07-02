from __future__ import annotations


MOCK_FORTUNE_RESULT = (
    "いま心を揺らしているのは、答えが見えないことより、考えても確信を持てない状態が続いていることかもしれません。\n\n"
    "今は無理に結論を出すより、自分の本音と相手や周囲への期待を分けて見ることで、流れが整いやすい時期に見えます。\n\n"
    "やりがちなのは、不安を消そうとして答えを急ぎ、小さな違和感を見落とすこと。焦るほど判断が相手任せになりやすそうです。\n\n"
    "今日は、いちばん気になっていることを一文だけ書き、その下に『本当はどうなってほしいか』を一つ添えてみてください。"
)


class MockOpenAITextClient:
    """開発時に外部通信なしで固定鑑定文を返すクライアント。"""

    def generate_fortune(self, **_kwargs) -> str:
        return MOCK_FORTUNE_RESULT
