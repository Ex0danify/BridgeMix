"""
Roland Bridge Cast SysEx address and value constants.

Split into domain-specific sub-modules for easier navigation:
  sections  — protocol framing: header, section/type bytes, sync sizes, USB IDs
  channel   — per-channel: faders, mutes, LED colours, strip config, meters
  mic_fx    — mic effects: source, phantom, gain, cleanup, EQ, chat FX
  voice_fx  — voice effects and reverb
  game_fx   — game EQ, limiter, virtual surround
  global_   — system settings, profiles, output routing, CC numbers

All names are re-exported here so existing code using
  ``from bridgemix.device import constants as C``
continues to work without modification.
"""

from bridgemix.device.constants.sections import *   # noqa: F401, F403
from bridgemix.device.constants.channel  import *   # noqa: F401, F403
from bridgemix.device.constants.mic_fx   import *   # noqa: F401, F403
from bridgemix.device.constants.voice_fx import *   # noqa: F401, F403
from bridgemix.device.constants.game_fx  import *   # noqa: F401, F403
from bridgemix.device.constants.global_  import *   # noqa: F401, F403
