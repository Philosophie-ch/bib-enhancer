from enum import Enum


class BibTeXEntryTypeEnum(Enum):
    """
    An enumeration of the possible types of bibtex entries.
    """

    ARTICLE = "article"
    BOOK = "book"
    INCOLLECTION = "incollection"
    INPROCEEDINGS = "inproceedings"
    MASTERSTHESIS = "mastersthesis"
    MISC = "misc"
    PHDTHESIS = "phdthesis"
    PROCEEDINGS = "proceedings"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"


class LanguageIDEnum(Enum):
    """
    An enumeration of the possible values of language unique names.
    """

    CATALAN = "catalan"
    CZECH = "czech"
    DANISH = "danish"
    DUTCH = "dutch"
    ENGLISH = "english"
    FRENCH = "french"
    GREEK = "greek"
    ITALIAN = "italian"
    LATIN = "latin"
    LITHUANIAN = "lithuanian"
    NGERMAN = "ngerman"
    POLISH = "polish"
    PORTUGUESE = "portuguese"
    ROMANIAN = "romanian"
    RUSSIAN = "russian"
    SLOVAK = "slovak"
    SPANISH = "spanish"
    SWEDISH = "swedish"
    UNKNOWN = "unknown"


class EpochEnum(Enum):
    """
    An enumeration of the possible values of epoch unique names.
    """

    ANCIENT_PHILOSOPHY = "ancient-philosophy"
    ANCIENT_SCIENTISTS = "ancient-scientists"
    AUSTRIAN_PHILOSOPHY = "austrian-philosophy"
    BRITISH_IDEALISM = "british-idealism"
    CLASSICS = "classics"
    CONTEMPORARIES = "contemporaries"
    CONTEMPORARY_SCIENTISTS = "contemporary-scientists"
    CONTINENTAL_PHILOSOPHY = "continental-philosophy"
    CRITICAL_THEORY = "critical-theory"
    CYNICS = "cynics"
    ENLIGHTENMENT = "enlightenment"
    EXISTENTIALISM = "existentialism"
    EXOTIC_PHILOSOPHY = "exotic-philosophy"
    GERMAN_IDEALISM = "german-idealism"
    GERMAN_RATIONALISM = "german-rationalism"
    GESTALT_PSYCHOLOGY = "gestalt-psychology"
    HERMENEUTICS = "hermeneutics"
    ISLAMIC_PHILOSOPHY = "islamic-philosophy"
    MATHEMATICIANS = "mathematicians"
    MEDIEVAL_PHILOSOPHY = "medieval-philosophy"
    MODERN_PHILOSOPHY = "modern-philosophy"
    MODERN_SCIENTISTS = "modern-scientists"
    NEOKANTIANISM = "neokantianism"
    NEO_KANTIANISM = "neo-kantianism"
    NEOPLATONISM = "neoplatonism"
    NEW_REALISM = "new-realism"
    ORDINARY_LANGUAGE_PHILOSOPHY = "ordinary-language-philosophy"
    PHENOMENOLOGY = "phenomenology"
    POLISH_LOGIC = "polish-logic"
    PRAGMATISM = "pragmatism"
    PRESOCRATICS = "presocratics"
    RENAISSANCE = "renaissance"
    STOICS = "stoics"
    THEOLOGIANS = "theologians"
    VIENNA_CIRCLE = "vienna-circle"


class BibInfoSourceEnum(Enum):
    """
    An enumeration of the possible values for the sources of information about bibliographic entries. For example, Crossref, Google Scholar, etc.
    """

    BLUMBIB = "blumbib"
    CROSSREF = "crossref"
