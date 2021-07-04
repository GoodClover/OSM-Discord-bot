# /bin/python3
import re

SS = r"(?<!\/|\w)"  # Safe Start
SE = r"(?!\/|\w)"  # Safe End
DECIMAL = r"[+-]?(?:[0-9]*\.)?[0-9]+"
POS_INT = r"[0-9]+"
### Inline linking ###
ELM_INLINE = rf"{SS}(node|way|relation)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
CHANGESET_INLINE = rf"{SS}(changeset)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
NOTE_INLINE = rf"{SS}(note)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
USER_INLINE = rf"{SS}user\/[\w\-_]+{SE}"
# FIXME: For some reason this allows stuff after the end of the map fragment.
MAP_FRAGMENT_INLINE = rf"{SS}#map={POS_INT}\/{DECIMAL}\/{DECIMAL}{SE}"
MAP_FRAGEMT_CAPTURING = rf"#map=({POS_INT})\/({DECIMAL})\/({DECIMAL})"
ELM_INLINE = re.compile(ELM_INLINE, re.IGNORECASE)
CHANGESET_INLINE = re.compile(CHANGESET_INLINE, re.IGNORECASE)
NOTE_INLINE = re.compile(NOTE_INLINE, re.IGNORECASE)
USER_INLINE = re.compile(USER_INLINE, re.IGNORECASE)
MAP_FRAGMENT_INLINE = re.compile(MAP_FRAGMENT_INLINE, re.IGNORECASE)
INTEGER = re.compile(POS_INT)
POTLATCH = "use potlatch"
