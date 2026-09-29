# Third-party notices

Zundanen v1.1.0 uses several third-party projects. This source archive does not include the large generated `runtime/` environments. The Windows-native Aalto/Kaldi runtime may be distributed as a separate Zundanen release asset prepared from the projects listed below; retain the applicable upstream license notices with any redistributed binaries or model assets.

- **Finnish-NLP/Chatterbox-Finnish** — MIT license  
  https://huggingface.co/Finnish-NLP/Chatterbox-Finnish
- **ResembleAI Chatterbox** — MIT license  
  https://github.com/resemble-ai/chatterbox
- **Retrieval-based-Voice-Conversion-WebUI (RVC)** — MIT license / upstream notices apply  
  https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- **FFmpeg (Gyan Windows build)** — FFmpeg/Gyan build licensing applies  
  https://www.gyan.dev/ffmpeg/builds/  
  https://ffmpeg.org/legal.html
- **Python** — Python Software Foundation license  
  https://www.python.org/
- **PyTorch** — BSD-style license  
  https://pytorch.org/
- **Docker Desktop** — Docker Subscription Service Agreement applies  
  https://docs.docker.com/subscription-billing/desktop-license/  
  Used only by the legacy Accent compatibility fallback. Docker Desktop is not redistributed
  or installed by the normal v1.1.0 setup. Developers may install it separately when explicitly
  testing the legacy Docker backend.
- **Aalto Speech / Finnish Forced Alignment** — MIT license  
  https://github.com/aalto-speech/finnish-forced-alignment
- **Lingsoft / aalto-kaldi-align-elg** — MIT license  
  https://github.com/lingsoft/aalto-kaldi-align-elg  
  Source used by the v1.1 Windows-native runtime preparation workflow to export selected Aalto Finnish alignment model/configuration/G2P assets. The Docker image itself is not redistributed. The separate native runtime asset includes the applicable Aalto MIT license and Lingsoft source notice.
- **Kaldi** — Apache License 2.0  
  https://github.com/kaldi-asr/kaldi  
  Zundanen v1.1 uses selected Kaldi Windows executables for the native Aalto alignment backend. Kaldi binaries are distributed separately in `Zundanen-Aalto-Native-v1.1.0.zip`; that runtime asset includes the Apache 2.0 license and a Kaldi attribution notice.
- **Intel oneMKL** — Intel software license terms apply  
  https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl-download.html  
  The tested Windows Kaldi build uses oneMKL. The Accent support installer can install oneMKL through WinGet when the packaged Kaldi executables require it. oneMKL is not included in this source archive.
- **WORLD Vocoder** — modified BSD license  
  https://github.com/mmorise/World  
  Used by the optional Accent editor for speech analysis, manipulation, and resynthesis.
- **PyWORLD** — MIT license  
  https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder  
  Python wrapper installed into the local RVC environment by the v1.1.0 setup for Accent editing; not redistributed in this repository or native runtime asset.

Character voices, datasets, RVC `.pth` files and `.index` files may carry separate rights or usage conditions that are not granted by this application's license.


## Desktop launcher and UI dependencies

- **pywebview** — BSD 3-Clause License  
  https://github.com/r0x0r/pywebview
- **Microsoft Edge WebView2 Runtime** — Microsoft distribution/license terms apply  
  https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
- **Go standard library/runtime** — BSD-style License  
  https://go.dev/LICENSE

`Zundanen.exe` is a small launcher compiled with Go and therefore contains portions of the Go runtime/standard library.

### Go license

Copyright 2009 The Go Authors.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the distribution.
* Neither the name of Google LLC nor the names of its contributors may
  be used to endorse or promote products derived from this software
  without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
