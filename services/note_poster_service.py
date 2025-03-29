# services/note_poster_service.py
import logging
import re
import time
from datetime import datetime

import pyperclip
from playwright.sync_api import sync_playwright

from models.article import Article


class NotePosterService:
    """Noteに記事を投稿するサービス"""

    def __init__(self, email: str, password: str):
        """
        Note投稿サービスの初期化

        Args:
            email: Noteアカウントのメールアドレス
            password: Noteアカウントのパスワード
        """
        self.email = email
        self.password = password

    def remove_markdown_block(self, text: str) -> str:
        # ```markdown で始まり、``` で終わるブロックを削除
        cleaned_text = re.sub(r"```markdown\n(.*?)```", r"\1", text, flags=re.DOTALL)
        return cleaned_text

    def parse_markdown(self, markdown_content: str) -> tuple:
        """
        Markdown形式の記事を解析してタイトルとセクションに分割

        Args:
            markdown_content: Markdown形式の記事内容

        Returns:
            tuple: (タイトル, セクションのリスト)
        """
        logging.info("Markdown記事を解析中")

        markdown_content = self.remove_markdown_block(markdown_content)

        # 最初の# で始まる行をタイトルとして扱う
        title_match = re.search(r"^# (.+)", markdown_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # タイトル行を除外
            content = markdown_content.replace(title_match.group(0), "", 1).strip()
        else:
            # タイトルが見つからない場合は「無題」
            title = "無題の記事"
            content = markdown_content

        logging.info(f"記事タイトル: {title}")

        # セクションに分割（見出しと段落）
        sections = []

        # 見出しのパターン
        heading_pattern = re.compile(r"^(#{1,3}) (.+)", re.MULTILINE)

        # セクションを抽出
        last_pos = 0
        for match in heading_pattern.finditer(content):
            # 前のセクションの終わりから現在の見出しの前までをパラグラフとして追加
            paragraph_content = content[last_pos : match.start()].strip()
            if paragraph_content:
                sections.append({"type": "paragraph", "content": paragraph_content})

            # 見出しを追加
            heading_level = len(match.group(1))
            heading_text = match.group(1) + " " + match.group(2).strip()
            sections.append(
                {"type": f"heading{heading_level}", "content": heading_text}
            )

            last_pos = match.end()

        # 最後のセクション
        if last_pos < len(content):
            paragraph_content = content[last_pos:].strip()
            if paragraph_content:
                sections.append({"type": "paragraph", "content": paragraph_content})

        logging.info(f"セクション数: {len(sections)}")
        return title, sections

    def post_article(self, article: Article) -> bool:
        """
        記事をNoteに投稿

        Args:
            article: 投稿する記事

        Returns:
            bool: 投稿が成功したかどうか
        """
        logging.info(f"記事「{article.title}」をNoteに投稿します")

        # 改善された記事があればそれを使用、なければ通常の記事を使用
        content = (
            article.improved_content if article.improved_content else article.content
        )

        # Markdown記事を解析
        title, sections = self.parse_markdown(content)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            try:
                # ログイン
                logging.info("noteへのログインを開始します")
                page.goto("https://note.com/login")
                page.wait_for_selector("#email", timeout=10000)
                page.wait_for_selector("#password", timeout=10000)
                page.wait_for_load_state("networkidle")
                time.sleep(1)

                page.fill("#email", self.email)
                page.fill("#password", self.password)
                time.sleep(1)
                page.click('button:has(div:has-text("ログイン"))')
                page.wait_for_load_state("networkidle")
                logging.info("✅ noteにログイン成功")
                time.sleep(1)

                # 新規記事作成ページにアクセス
                logging.info("📝 noteの新規記事作成ページにアクセス中...")
                page.goto("https://note.com/notes/new")
                page.wait_for_load_state("networkidle")

                # タイトル入力
                page.fill('textarea[placeholder="記事タイトル"]', title)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                logging.info(f"📝 記事タイトル '{title}' を入力しました")

                # セクションごとに処理
                for section in sections:
                    section_type = section["type"]
                    content = section["content"]

                    if section_type == "paragraph":
                        # 段落テキストを入力
                        logging.info(f"📝 段落を入力中: {content[:30]}...")
                        pyperclip.copy(content)
                        page.keyboard.press("Control+V")
                        page.keyboard.press("Enter")
                        page.keyboard.press("Enter")

                    elif section_type.startswith("heading"):
                        # 見出しを入力
                        level = int(section_type[-1])
                        logging.info(f"📝 見出し{level}を入力中: {content}")

                        # クリップボードにコピー
                        pyperclip.copy(content)

                        # 貼り付け
                        page.keyboard.press("Control+V")
                        page.keyboard.press("Enter")

                    time.sleep(0.5)

                # 記事を下書き保存
                logging.info("💾 記事を下書きとして保存します")
                page.click("button:has-text('保存')")
                page.wait_for_load_state("networkidle")
                logging.info("✅ 記事の下書き保存が完了しました")
                time.sleep(2)

                # 公開ボタンがあれば記事を公開
                try:
                    if page.is_visible("button:has-text('公開する')"):
                        logging.info("🌐 記事を公開します")
                        page.click("button:has-text('公開する')")
                        page.wait_for_selector(
                            "button:has-text('有料記事として公開する')", timeout=5000
                        )
                        page.click("button:has-text('有料記事として公開する')")
                        page.wait_for_load_state("networkidle")
                        logging.info("✅ 記事の公開が完了しました")

                        # 記事の状態を更新
                        article.status = "published"
                        article.published_at = datetime.now()
                        return True
                except Exception as e:
                    logging.warning(f"記事の公開中にエラーが発生しました: {str(e)}")

                return True

            except Exception as e:
                logging.error(f"❌ エラー: {str(e)}")
                return False
            finally:
                context.close()
                browser.close()
                logging.info("🚀 Playwright処理が完了しました")