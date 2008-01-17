from pygments.style import Style
from pygments.token import Keyword, Name, Comment, String, Error, \
     Number, Operator, Generic, Punctuation


# Style for Pygments source highlighter
class ApydiaStyle(Style):
    default_style = ""
    styles = {
        Comment:        "italic #999",
        Keyword:        "#5E80E6",
        Name:           "#000",
        Name.Function:  "#E85833",
        Name.Class:     "#E85833",
        String:         "bg:#F8F8F8 #444",
        Punctuation:    "#444",
        Operator:       "#E85833",
        Error:          "bg:#FFFFFF border:#F04 #802"
    }

