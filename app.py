"""터미널용 간단 게시판."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

DATA_FILE = Path("board.json")


def load_posts():
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_posts(posts):
    DATA_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def find_post(posts, post_id):
    for post in posts:
        if post["id"] == post_id:
            return post
    return None


def cmd_add(args):
    posts = load_posts()
    next_id = max((p["id"] for p in posts), default=0) + 1
    posts.append({
        "id": next_id,
        "title": args.title,
        "content": args.content,
        "author": args.author,
        "date": date.today().isoformat(),
    })
    save_posts(posts)
    print(f"{next_id}번 글이 등록되었습니다.")


def cmd_list(args):
    posts = load_posts()
    if not posts:
        print("등록된 글이 없습니다.")
        return
    if args.keyword:
        keyword = args.keyword.lower()
        posts = [
            p for p in posts
            if keyword in p["title"].lower() or keyword in p["content"].lower()
        ]
        if not posts:
            print("검색 결과가 없습니다.")
            return
    for post in sorted(posts, key=lambda p: p["id"], reverse=True):
        print(f"[{post['id']}] {post['title']} - {post['author']} ({post['date']})")


def cmd_show(args):
    post = find_post(load_posts(), args.id)
    if post is None:
        print(f"{args.id}번 글을 찾을 수 없습니다.")
        return 1
    print(f"제목: {post['title']}")
    print(f"작성자: {post['author']}")
    print(f"날짜: {post['date']}")
    print()
    print(post["content"])


def cmd_delete(args):
    posts = load_posts()
    post = find_post(posts, args.id)
    if post is None:
        print(f"{args.id}번 글을 찾을 수 없습니다.")
        return 1
    posts.remove(post)
    save_posts(posts)
    print(f"{args.id}번 글이 삭제되었습니다.")


def build_parser():
    parser = argparse.ArgumentParser(description="간단한 게시판")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="글 쓰기")
    add.add_argument("title", help="제목")
    add.add_argument("content", help="내용")
    add.add_argument("--author", default="익명", help="작성자 (기본: 익명)")
    add.set_defaults(func=cmd_add)

    lst = sub.add_parser("list", help="글 목록")
    lst.add_argument("--keyword", help="제목이나 내용에 이 단어가 들어간 글만 보기")
    lst.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="글 보기")
    show.add_argument("id", type=int, help="글 번호")
    show.set_defaults(func=cmd_show)

    delete = sub.add_parser("delete", help="글 삭제")
    delete.add_argument("id", type=int, help="글 번호")
    delete.set_defaults(func=cmd_delete)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
