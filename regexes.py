# /bin/python3
import re

SS = r"(?<!\/|\w)"  # Safe Start
SE = r"(?!\/|\w)"  # Safe End
DECIMAL = r"[+-]?(?:[0-9]*\.)?[0-9]+"
POS_INT = r"[0-9]+"
USERNAME = r"[\w\-_]+"
### Inline linking ###
ELM_INLINE = rf"{SS}(node|way|relation)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
CHANGESET_INLINE = rf"{SS}(changeset)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
NOTE_INLINE = rf"{SS}(note)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
USER_INLINE = rf"{SS}(user)(s? |\/)({USERNAME}(?:(?:, | and | or | )(?:{USERNAME}))*){SE}"
# FIXME: For some reason this allows stuff after the end of the map fragment.
MAP_FRAGMENT_INLINE = rf"{SS}#map={POS_INT}\/{DECIMAL}\/{DECIMAL}{SE}"
MAP_FRAGEMT_CAPTURING = rf"#map=({POS_INT})\/({DECIMAL})\/({DECIMAL})"
POTLATCH = r"(ha(ve|d|s) )?us(ed|ing|es?) potlatch"
ELM_INLINE = re.compile(ELM_INLINE, re.IGNORECASE)
CHANGESET_INLINE = re.compile(CHANGESET_INLINE, re.IGNORECASE)
NOTE_INLINE = re.compile(NOTE_INLINE, re.IGNORECASE)
USER_INLINE = re.compile(USER_INLINE, re.IGNORECASE)
MAP_FRAGMENT_INLINE = re.compile(MAP_FRAGMENT_INLINE, re.IGNORECASE)
INTEGER = re.compile(POS_INT)
STRING = re.compile(USERNAME)
POTLATCH = re.compile(POTLATCH, re.IGNORECASE)


def find_matches(pattern, phrase):
    # Type: re.Pattern
    # Finds matches for inline elements.
    output = list()
    for elm in pattern.findall(phrase):
        output.append((elm[0].lower(), tuple(STRING.findall(elm[2])), elm[1]))
    return output
