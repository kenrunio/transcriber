# Third-party software in the Transcriber installer

Transcriber itself is MIT-licensed (LICENSE). The installer bundles the
software below, each under its own licence. The speech, speaker and
punctuation models are not bundled: users download the ones they choose,
and the Models page shows each one's licence. NVIDIA's GPU libraries are
not bundled either; the app downloads them from PyPI on request.

## Python packages

| Package | Version | Licence | Project |
|---|---|---|---|
| anyio | 4.15.1 | MIT | https://github.com/agronholm/anyio |
| av | 18.1.0 | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| blinker | 1.9.0 | MIT License | https://github.com/pallets-eco/blinker/ |
| bottle | 0.13.4 | MIT License | https://github.com/bottlepy/bottle |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| cloudpickle | 3.1.2 | BSD License | https://github.com/cloudpipe/cloudpickle |
| clr_loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| colorama | 0.4.6 | BSD License | https://github.com/tartley/colorama |
| ctranslate2 | 4.8.3 | MIT | https://github.com/OpenNMT/CTranslate2 |
| faster-whisper | 1.2.1 | MIT License | https://github.com/SYSTRAN/faster-whisper |
| filelock | 4.2.4 | MIT | https://github.com/tox-dev/py-filelock |
| Flask | 3.1.3 | BSD-3-Clause | https://github.com/pallets/flask/ |
| flatbuffers | 25.12.19 | Apache Software License | https://github.com/google/flatbuffers |
| fsspec | 2026.9.0 | BSD-3-Clause | https://github.com/fsspec/filesystem_spec |
| h11 | 0.16.0 | MIT License | https://github.com/python-hyper/h11 |
| hf-xet | 1.7.0 | Apache-2.0 | https://github.com/huggingface/xet-core |
| httpcore2 | 2.15.1 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| httpx2 | 2.15.1 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| huggingface_hub | 2.2.0 | Apache Software License | https://github.com/huggingface/huggingface_hub |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| itsdangerous | 2.2.0 | BSD License | https://github.com/pallets/itsdangerous/ |
| Jinja2 | 3.1.6 | BSD License | https://github.com/pallets/jinja/ |
| joblib | 1.6.0 | BSD-3-Clause | https://joblib.readthedocs.io |
| lxml | 6.1.3 | BSD-3-Clause | https://github.com/lxml/lxml |
| MarkupSafe | 3.0.4 | BSD-3-Clause | https://github.com/pallets/markupsafe/ |
| narwhals | 2.27.1 | MIT | https://github.com/narwhals-dev/narwhals |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| onnxruntime | 1.31.0 | MIT License | https://onnxruntime.ai |
| protobuf | 7.36.2 | 3-Clause BSD License | https://developers.google.com/protocol-buffers/ |
| proxy_tools | 0.1.0 | MIT License | http://github.com/jtushman/proxy_tools |
| pycparser | 3.11 | BSD-3-Clause | https://github.com/eliben/pycparser |
| python-docx | 1.2.0 | MIT License | https://github.com/python-openxml/python-docx |
| pythonnet | 3.2.1 | MIT | https://pythonnet.github.io/ |
| pywebview | 6.2.1 | BSD License | https://pywebview.flowrl.com/ |
| PyYAML | 6.0.3 | MIT License | https://github.com/yaml/pyyaml |
| scikit-learn | 1.9.1 | BSD-3-Clause | https://scikit-learn.org |
| scipy | 1.17.1 | BSD License | https://scipy.org/ |
| soundfile | 0.14.0 | BSD License | https://github.com/bastibe/python-soundfile |
| threadpoolctl | 3.7.0 | BSD-3-Clause | https://github.com/joblib/threadpoolctl |
| tokenizers | 0.23.3 | Apache Software License | https://github.com/huggingface/tokenizers |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | https://tqdm.github.io |
| truststore | 0.10.5 | MIT | https://github.com/sethmlarson/truststore |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| Werkzeug | 3.1.9 | BSD-3-Clause | https://github.com/pallets/werkzeug/ |

## Native libraries inside those packages

| Library | Version | Licence | Project | Notes |
|---|---|---|---|---|
| Python | 3.13 | PSF-2.0 | https://www.python.org/ | the interpreter, python313.dll |
| FFmpeg libraries (in PyAV) | 8.1 | LGPL-3.0-or-later | https://ffmpeg.org/ | avcodec, avformat, avutil, ...; source: https://ffmpeg.org/download.html, build: https://github.com/PyAV-Org/pyav-ffmpeg |
| x264 (in PyAV) |  | GPL-2.0-or-later | https://www.videolan.org/developers/x264.html | H.264 encoder linked by FFmpeg; not used by Transcriber; source: https://code.videolan.org/videolan/x264 |
| x265 (in PyAV) |  | GPL-2.0-or-later | https://www.videolan.org/developers/x265.html | H.265 encoder linked by FFmpeg; not used by Transcriber; source: https://bitbucket.org/multicoreware/x265_git |
| LAME (in PyAV) |  | LGPL-2.0-or-later | https://lame.sourceforge.io/ |  |
| libvpx, dav1d, SVT-AV1, Opus, libwebp, opencore-amr (in PyAV) |  | BSD-style / Apache-2.0 | https://github.com/PyAV-Org/pyav-ffmpeg | codec libraries linked by FFmpeg |
| libsndfile (in soundfile) |  | LGPL-2.1-or-later | https://libsndfile.github.io/libsndfile/ |  |
| OpenBLAS (in NumPy and SciPy) |  | BSD-3-Clause | https://www.openblas.net/ |  |
| Intel OpenMP runtime, libiomp5md (in CTranslate2) |  | Intel Simplified Software License | https://github.com/OpenNMT/CTranslate2 |  |
| OpenSSL | 3 | Apache-2.0 | https://www.openssl.org/ | libcrypto, libssl |
| SQLite |  | Public domain | https://www.sqlite.org/ |  |
| Microsoft Edge WebView2 loader (in pywebview) |  | Microsoft WebView2 SDK licence (BSD-style) | https://www.nuget.org/packages/Microsoft.Web.WebView2 |  |

The full licence texts are in each package's folder inside the installed
program (`_internal\<package>*.dist-info`), and at the projects above. The
source code of the LGPL and GPL libraries is available from the links given.
