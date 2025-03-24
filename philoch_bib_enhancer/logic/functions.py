from philoch_bib_enhancer.logic.models import Author


def author_full_name(author: Author) -> str:

    if author.family_name is None:
        return author.given_name

    return f"{author.family_name}, {author.given_name}"
