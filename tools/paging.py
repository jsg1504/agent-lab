"""긴 본문을 구간으로 나눠 읽게 해 주는 공통 부분."""


def window(text: str, offset: int, limit: int) -> str:
    """text의 offset부터 limit자를 돌려준다. 남은 부분이 있으면 이어 읽는 법을 끝에 붙인다.

    말없이 자르면 모델이 뒷부분을 얻으려고 같은 호출을 되풀이한다.
    """
    offset = max(int(offset), 0)
    if offset and offset >= len(text):
        return f"offset({offset})이 본문 길이({len(text)}자)를 넘었습니다. 더 읽을 내용이 없습니다."
    end = offset + limit
    if offset == 0 and end >= len(text):
        return text
    note = f"(전체 {len(text)}자 중 {offset}~{min(end, len(text))}자."
    note += f" 이어 읽으려면 offset={end}로 다시 불러라.)" if end < len(text) else " 끝까지 읽었다.)"
    return f"{text[offset:end]}\n\n{note}"
