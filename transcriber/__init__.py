__version__ = "0.1.0"

# The GitHub repository ("owner/name") whose releases the app checks for a newer
# version. Empty: no update checks.
UPDATE_REPO = "kenrunio/transcriber"

# The publisher the release installers are signed as: text that must appear in
# the signing certificate's subject. With SignPath Foundation's free signing for
# open source that is "CN=SignPath Foundation" (shared by every project they
# sign, so the installer must also call itself "Transcriber": updates.trusted).
# The app installs an update itself only when Windows says the download is
# validly signed by it. Empty (no signed builds yet): it only offers a link.
UPDATE_PUBLISHER = ""
