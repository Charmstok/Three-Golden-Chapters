from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import zipfile

from chapter import parse_chapter_heading
from epub import parse_container_rootfile, parse_opf_spine, read_text_from_zip
from model import Chapter
from text_utils import norm_text
from xhtml import iter_text_blocks_from_xhtml


def extract_first_chapters(epub_path: Path, *, max_chapters: int = 3) -> List[Chapter]:
    """从 EPUB 中抽取前 max_chapters 章。

    返回值：每章一个 Chapter，其中 paragraphs 只包含正文段落；章节标题不计入 paragraph_id。

    为了减少误判，这里采用“两段式”策略：
    - 优先以“第x章/节/回 ...”作为分章起点（避免在书前信息/目录/设定里把“2、xxx”误当章节）。
    - 如果完全找不到“第x章/节/回 ...”，再退化为允许从头使用“x、标题 / x. 标题”作为起点。
    """

    def scan(*, allow_numbered_before_start: bool) -> List[Chapter]:
        out: List[Chapter] = []
        current: Optional[Chapter] = None
        started = 0

        with zipfile.ZipFile(epub_path, "r") as zf:
            opf_path = parse_container_rootfile(zf)
            spine = parse_opf_spine(zf, opf_path)

            for item in spine:
                if item.href not in zf.namelist():
                    # 少数 EPUB 的 spine 引用可能缺失文件：直接跳过。
                    continue

                xhtml = read_text_from_zip(zf, item.href)

                for block in iter_text_blocks_from_xhtml(xhtml):
                    # allow_numbered_before_start=False 时：在进入正文前不允许用“x、标题/x.标题”触发开始；
                    # 一旦开始后仍允许用它匹配后续章节（兼容不同排版）。
                    parsed = parse_chapter_heading(
                        block,
                        allow_numbered=(allow_numbered_before_start or started > 0),
                    )
                    if parsed:
                        ch_no, ch_title = parsed

                        if started == 0:
                            started = 1
                            current = Chapter(no=ch_no, title=ch_title, paragraphs=[])
                            continue

                        if started >= max_chapters:
                            # 遇到第 (max_chapters+1) 个章节标题：结束并返回。
                            if current is not None:
                                out.append(current)
                            return out

                        if current is not None:
                            out.append(current)
                        started += 1
                        current = Chapter(no=ch_no, title=ch_title, paragraphs=[])
                        continue

                    if current is None:
                        continue

                    t = norm_text(block)
                    if t:
                        current.paragraphs.append(t)

        if current is not None:
            out.append(current)

        return out[:max_chapters]

    # 优先以“第x章/节/回 ...”作为起点；若失败，再退化允许从头用“x、标题/x.标题”。
    primary = scan(allow_numbered_before_start=False)
    if primary:
        return primary
    return scan(allow_numbered_before_start=True)