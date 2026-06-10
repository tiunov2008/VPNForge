#!/usr/bin/env bash

set -e

# colors
GRN='\033[1;32m'
RED='\033[1;31m'
YEL='\033[1;33m'
NC='\033[0m'

# fingerprint REALITY
FINGERPRINT="firefox"

gen_token() {
    openssl rand -base64 "$1" | tr -dc 'A-Za-z0-9' | head -c "$1"
}

gen_path() {
    openssl rand -base64 15 | tr -dc 'a-z0-9' | head -c 6
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$PROJECT_DIR/nginx/default.conf"
HTML_DIR="$PROJECT_DIR/nginx/html"
XRAY_CONFIG_PATH="$PROJECT_DIR/xray/config.json"
LE_DIR="$PROJECT_DIR/letsencrypt"
CERT_DIR="/var/lib/xray/cert"

mkdir -p "$PROJECT_DIR/nginx" "$HTML_DIR" "$PROJECT_DIR/xray"

base64 -d > "$HTML_DIR/index.html" <<'EOF'
PCFkb2N0eXBlIGh0bWw+DQo8aHRtbCBsYW5nPSJydSI+DQo8aGVhZD4NCiAgPG1ldGEgY2hhcnNl
dD0idXRmLTgiPg0KICA8bWV0YSBuYW1lPSJ2aWV3cG9ydCIgY29udGVudD0id2lkdGg9ZGV2aWNl
LXdpZHRoLCBpbml0aWFsLXNjYWxlPTEiPg0KICA8dGl0bGU+0KHQvtC90JzQsNGA0LrQtdGCIOKA
lCDQvNCw0YLRgNCw0YHRiyDQuCDQsNC60YHQtdGB0YHRg9Cw0YDRiyDQtNC70Y8g0YHQvdCwPC90
aXRsZT4NCiAgPG1ldGEgbmFtZT0iZGVzY3JpcHRpb24iIGNvbnRlbnQ9ItCY0L3RhNC+0YDQvNCw
0YbQuNC+0L3QvdCw0Y8g0YHRgtGA0LDQvdC40YbQsCDQvNCw0LPQsNC30LjQvdCwINC80LDRgtGA
0LDRgdC+0LIsINC/0L7QtNGD0YjQtdC6INC4INCw0LrRgdC10YHRgdGD0LDRgNC+0LIg0LTQu9GP
INC60L7QvNGE0L7RgNGC0L3QvtCz0L4g0YHQvdCwLiI+DQogIDxtZXRhIG5hbWU9InJvYm90cyIg
Y29udGVudD0iaW5kZXgsZm9sbG93Ij4NCiAgPHN0eWxlPg0KICAgIDpyb290IHsNCiAgICAgIC0t
Ymc6ICNmN2YzZWQ7DQogICAgICAtLWNhcmQ6ICNmZmZmZmY7DQogICAgICAtLXRleHQ6ICMxZjI5
MzM7DQogICAgICAtLW11dGVkOiAjNjY3MDg1Ow0KICAgICAgLS1hY2NlbnQ6ICMyZjZmNWU7DQog
ICAgICAtLWFjY2VudC1kYXJrOiAjMjQ1OTRiOw0KICAgICAgLS1saW5lOiAjZTZkZWQyOw0KICAg
ICAgLS1zb2Z0OiAjZWVmNmYyOw0KICAgIH0NCg0KICAgICogew0KICAgICAgYm94LXNpemluZzog
Ym9yZGVyLWJveDsNCiAgICB9DQoNCiAgICBib2R5IHsNCiAgICAgIG1hcmdpbjogMDsNCiAgICAg
IGZvbnQtZmFtaWx5OiBBcmlhbCwgSGVsdmV0aWNhLCBzYW5zLXNlcmlmOw0KICAgICAgY29sb3I6
IHZhcigtLXRleHQpOw0KICAgICAgYmFja2dyb3VuZDogdmFyKC0tYmcpOw0KICAgICAgbGluZS1o
ZWlnaHQ6IDEuNTU7DQogICAgfQ0KDQogICAgaGVhZGVyIHsNCiAgICAgIGJhY2tncm91bmQ6DQog
ICAgICAgIHJhZGlhbC1ncmFkaWVudChjaXJjbGUgYXQgMjAlIDIwJSwgcmdiYSg0NywgMTExLCA5
NCwgMC4xNiksIHRyYW5zcGFyZW50IDI4JSksDQogICAgICAgIGxpbmVhci1ncmFkaWVudCgxMzVk
ZWcsICNmZmZhZjMgMCUsICNlOGYzZWUgMTAwJSk7DQogICAgICBib3JkZXItYm90dG9tOiAxcHgg
c29saWQgdmFyKC0tbGluZSk7DQogICAgfQ0KDQogICAgLndyYXAgew0KICAgICAgd2lkdGg6IG1p
bigxMTIwcHgsIGNhbGMoMTAwJSAtIDMycHgpKTsNCiAgICAgIG1hcmdpbjogMCBhdXRvOw0KICAg
IH0NCg0KICAgIC50b3BiYXIgew0KICAgICAgZGlzcGxheTogZmxleDsNCiAgICAgIGFsaWduLWl0
ZW1zOiBjZW50ZXI7DQogICAgICBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47DQogICAg
ICBwYWRkaW5nOiAxOHB4IDA7DQogICAgICBnYXA6IDIwcHg7DQogICAgfQ0KDQogICAgLmxvZ28g
ew0KICAgICAgZGlzcGxheTogZmxleDsNCiAgICAgIGFsaWduLWl0ZW1zOiBjZW50ZXI7DQogICAg
ICBnYXA6IDEwcHg7DQogICAgICBmb250LXdlaWdodDogNzAwOw0KICAgICAgZm9udC1zaXplOiAy
MHB4Ow0KICAgICAgbGV0dGVyLXNwYWNpbmc6IC0wLjAyZW07DQogICAgfQ0KDQogICAgLmxvZ28t
bWFyayB7DQogICAgICB3aWR0aDogMzRweDsNCiAgICAgIGhlaWdodDogMzRweDsNCiAgICAgIGJv
cmRlci1yYWRpdXM6IDEwcHg7DQogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1hY2NlbnQpOw0KICAg
ICAgZGlzcGxheTogZ3JpZDsNCiAgICAgIHBsYWNlLWl0ZW1zOiBjZW50ZXI7DQogICAgICBjb2xv
cjogd2hpdGU7DQogICAgICBmb250LXdlaWdodDogNzAwOw0KICAgIH0NCg0KICAgIG5hdiB7DQog
ICAgICBkaXNwbGF5OiBmbGV4Ow0KICAgICAgZ2FwOiAxOHB4Ow0KICAgICAgZmxleC13cmFwOiB3
cmFwOw0KICAgICAgZm9udC1zaXplOiAxNHB4Ow0KICAgICAgY29sb3I6IHZhcigtLW11dGVkKTsN
CiAgICB9DQoNCiAgICBuYXYgYSB7DQogICAgICBjb2xvcjogaW5oZXJpdDsNCiAgICAgIHRleHQt
ZGVjb3JhdGlvbjogbm9uZTsNCiAgICB9DQoNCiAgICBuYXYgYTpob3ZlciB7DQogICAgICBjb2xv
cjogdmFyKC0tYWNjZW50KTsNCiAgICB9DQoNCiAgICAuaGVybyB7DQogICAgICBkaXNwbGF5OiBn
cmlkOw0KICAgICAgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxLjFmciAwLjlmcjsNCiAgICAgIGdh
cDogNDJweDsNCiAgICAgIGFsaWduLWl0ZW1zOiBjZW50ZXI7DQogICAgICBwYWRkaW5nOiA3MnB4
IDAgODJweDsNCiAgICB9DQoNCiAgICBoMSB7DQogICAgICBtYXJnaW46IDAgMCAxOHB4Ow0KICAg
ICAgZm9udC1zaXplOiBjbGFtcCgzNnB4LCA1dncsIDYycHgpOw0KICAgICAgbGluZS1oZWlnaHQ6
IDEuMDU7DQogICAgICBsZXR0ZXItc3BhY2luZzogLTAuMDQ1ZW07DQogICAgfQ0KDQogICAgLmxl
YWQgew0KICAgICAgbWFyZ2luOiAwIDAgMjhweDsNCiAgICAgIG1heC13aWR0aDogNjIwcHg7DQog
ICAgICBjb2xvcjogdmFyKC0tbXV0ZWQpOw0KICAgICAgZm9udC1zaXplOiAxOHB4Ow0KICAgIH0N
Cg0KICAgIC5hY3Rpb25zIHsNCiAgICAgIGRpc3BsYXk6IGZsZXg7DQogICAgICBnYXA6IDEycHg7
DQogICAgICBmbGV4LXdyYXA6IHdyYXA7DQogICAgfQ0KDQogICAgLmJ0biB7DQogICAgICBkaXNw
bGF5OiBpbmxpbmUtYmxvY2s7DQogICAgICBwYWRkaW5nOiAxM3B4IDE4cHg7DQogICAgICBib3Jk
ZXItcmFkaXVzOiAxMnB4Ow0KICAgICAgdGV4dC1kZWNvcmF0aW9uOiBub25lOw0KICAgICAgZm9u
dC13ZWlnaHQ6IDcwMDsNCiAgICAgIGZvbnQtc2l6ZTogMTVweDsNCiAgICB9DQoNCiAgICAuYnRu
LXByaW1hcnkgew0KICAgICAgYmFja2dyb3VuZDogdmFyKC0tYWNjZW50KTsNCiAgICAgIGNvbG9y
OiB3aGl0ZTsNCiAgICB9DQoNCiAgICAuYnRuLXByaW1hcnk6aG92ZXIgew0KICAgICAgYmFja2dy
b3VuZDogdmFyKC0tYWNjZW50LWRhcmspOw0KICAgIH0NCg0KICAgIC5idG4tZ2hvc3Qgew0KICAg
ICAgY29sb3I6IHZhcigtLWFjY2VudC1kYXJrKTsNCiAgICAgIGJhY2tncm91bmQ6ICNmZmZmZmY7
DQogICAgICBib3JkZXI6IDFweCBzb2xpZCB2YXIoLS1saW5lKTsNCiAgICB9DQoNCiAgICAudmlz
dWFsIHsNCiAgICAgIGJhY2tncm91bmQ6IHZhcigtLWNhcmQpOw0KICAgICAgYm9yZGVyOiAxcHgg
c29saWQgdmFyKC0tbGluZSk7DQogICAgICBib3JkZXItcmFkaXVzOiAyOHB4Ow0KICAgICAgcGFk
ZGluZzogMjZweDsNCiAgICAgIGJveC1zaGFkb3c6IDAgMjRweCA3MHB4IHJnYmEoMzMsIDQzLCA1
NCwgMC4xMik7DQogICAgfQ0KDQogICAgLm1hdHRyZXNzIHsNCiAgICAgIGhlaWdodDogMjYwcHg7
DQogICAgICBib3JkZXItcmFkaXVzOiAyMnB4Ow0KICAgICAgYmFja2dyb3VuZDoNCiAgICAgICAg
bGluZWFyLWdyYWRpZW50KDEzNWRlZywgcmdiYSg0NywgMTExLCA5NCwgLjA4KSAyNSUsIHRyYW5z
cGFyZW50IDI1JSkgLTE4cHggMC8zNnB4IDM2cHgsDQogICAgICAgIGxpbmVhci1ncmFkaWVudCgy
MjVkZWcsIHJnYmEoNDcsIDExMSwgOTQsIC4wOCkgMjUlLCB0cmFuc3BhcmVudCAyNSUpIC0xOHB4
IDAvMzZweCAzNnB4LA0KICAgICAgICBsaW5lYXItZ3JhZGllbnQoMzE1ZGVnLCByZ2JhKDQ3LCAx
MTEsIDk0LCAuMDgpIDI1JSwgdHJhbnNwYXJlbnQgMjUlKSAwIDAvMzZweCAzNnB4LA0KICAgICAg
ICBsaW5lYXItZ3JhZGllbnQoNDVkZWcsIHJnYmEoNDcsIDExMSwgOTQsIC4wOCkgMjUlLCAjZmZm
IDI1JSkgMCAwLzM2cHggMzZweDsNCiAgICAgIGJvcmRlcjogMXB4IHNvbGlkICNlOGVjZTg7DQog
ICAgICBwb3NpdGlvbjogcmVsYXRpdmU7DQogICAgICBvdmVyZmxvdzogaGlkZGVuOw0KICAgIH0N
Cg0KICAgIC5tYXR0cmVzczo6YWZ0ZXIgew0KICAgICAgY29udGVudDogIiI7DQogICAgICBwb3Np
dGlvbjogYWJzb2x1dGU7DQogICAgICBsZWZ0OiAyOHB4Ow0KICAgICAgcmlnaHQ6IDI4cHg7DQog
ICAgICBib3R0b206IDI4cHg7DQogICAgICBoZWlnaHQ6IDU0cHg7DQogICAgICBib3JkZXItcmFk
aXVzOiAxNnB4Ow0KICAgICAgYmFja2dyb3VuZDogI2U5ZjNlZjsNCiAgICAgIGJvcmRlcjogMXB4
IHNvbGlkICNkOWU4ZTI7DQogICAgfQ0KDQogICAgLmJhZGdlLXJvdyB7DQogICAgICBkaXNwbGF5
OiBncmlkOw0KICAgICAgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiByZXBlYXQoMywgMWZyKTsNCiAg
ICAgIGdhcDogMTJweDsNCiAgICAgIG1hcmdpbi10b3A6IDE4cHg7DQogICAgfQ0KDQogICAgLmJh
ZGdlIHsNCiAgICAgIGJhY2tncm91bmQ6IHZhcigtLXNvZnQpOw0KICAgICAgYm9yZGVyOiAxcHgg
c29saWQgI2RjZWJlNTsNCiAgICAgIGJvcmRlci1yYWRpdXM6IDE2cHg7DQogICAgICBwYWRkaW5n
OiAxNHB4Ow0KICAgICAgdGV4dC1hbGlnbjogY2VudGVyOw0KICAgICAgZm9udC1zaXplOiAxM3B4
Ow0KICAgICAgY29sb3I6IHZhcigtLWFjY2VudC1kYXJrKTsNCiAgICAgIGZvbnQtd2VpZ2h0OiA3
MDA7DQogICAgfQ0KDQogICAgc2VjdGlvbiB7DQogICAgICBwYWRkaW5nOiA2MHB4IDA7DQogICAg
fQ0KDQogICAgLnNlY3Rpb24tdGl0bGUgew0KICAgICAgbWFyZ2luOiAwIDAgMTBweDsNCiAgICAg
IGZvbnQtc2l6ZTogMzJweDsNCiAgICAgIGxldHRlci1zcGFjaW5nOiAtMC4wM2VtOw0KICAgIH0N
Cg0KICAgIC5zZWN0aW9uLXRleHQgew0KICAgICAgbWFyZ2luOiAwIDAgMjZweDsNCiAgICAgIGNv
bG9yOiB2YXIoLS1tdXRlZCk7DQogICAgICBtYXgtd2lkdGg6IDcyMHB4Ow0KICAgIH0NCg0KICAg
IC5ncmlkIHsNCiAgICAgIGRpc3BsYXk6IGdyaWQ7DQogICAgICBncmlkLXRlbXBsYXRlLWNvbHVt
bnM6IHJlcGVhdCgzLCAxZnIpOw0KICAgICAgZ2FwOiAxOHB4Ow0KICAgIH0NCg0KICAgIC5jYXJk
IHsNCiAgICAgIGJhY2tncm91bmQ6IHZhcigtLWNhcmQpOw0KICAgICAgYm9yZGVyOiAxcHggc29s
aWQgdmFyKC0tbGluZSk7DQogICAgICBib3JkZXItcmFkaXVzOiAyMHB4Ow0KICAgICAgcGFkZGlu
ZzogMjRweDsNCiAgICAgIG1pbi1oZWlnaHQ6IDIxMHB4Ow0KICAgICAgYm94LXNoYWRvdzogMCAx
MnB4IDMwcHggcmdiYSgzMywgNDMsIDU0LCAwLjA2KTsNCiAgICB9DQoNCiAgICAuaWNvbiB7DQog
ICAgICB3aWR0aDogNDZweDsNCiAgICAgIGhlaWdodDogNDZweDsNCiAgICAgIGJvcmRlci1yYWRp
dXM6IDE0cHg7DQogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1zb2Z0KTsNCiAgICAgIGRpc3BsYXk6
IGdyaWQ7DQogICAgICBwbGFjZS1pdGVtczogY2VudGVyOw0KICAgICAgbWFyZ2luLWJvdHRvbTog
MTZweDsNCiAgICAgIGNvbG9yOiB2YXIoLS1hY2NlbnQpOw0KICAgICAgZm9udC1zaXplOiAyNHB4
Ow0KICAgIH0NCg0KICAgIC5jYXJkIGgzIHsNCiAgICAgIG1hcmdpbjogMCAwIDhweDsNCiAgICAg
IGZvbnQtc2l6ZTogMjBweDsNCiAgICB9DQoNCiAgICAuY2FyZCBwIHsNCiAgICAgIG1hcmdpbjog
MDsNCiAgICAgIGNvbG9yOiB2YXIoLS1tdXRlZCk7DQogICAgICBmb250LXNpemU6IDE1cHg7DQog
ICAgfQ0KDQogICAgLnByb2R1Y3RzIHsNCiAgICAgIGdyaWQtdGVtcGxhdGUtY29sdW1uczogcmVw
ZWF0KDQsIDFmcik7DQogICAgfQ0KDQogICAgLnByb2R1Y3Qgew0KICAgICAgYmFja2dyb3VuZDog
dmFyKC0tY2FyZCk7DQogICAgICBib3JkZXI6IDFweCBzb2xpZCB2YXIoLS1saW5lKTsNCiAgICAg
IGJvcmRlci1yYWRpdXM6IDIwcHg7DQogICAgICBvdmVyZmxvdzogaGlkZGVuOw0KICAgICAgYm94
LXNoYWRvdzogMCAxMnB4IDMwcHggcmdiYSgzMywgNDMsIDU0LCAwLjA1KTsNCiAgICB9DQoNCiAg
ICAucHJvZHVjdC1pbWcgew0KICAgICAgaGVpZ2h0OiAxMzJweDsNCiAgICAgIGJhY2tncm91bmQ6
DQogICAgICAgIGxpbmVhci1ncmFkaWVudCgxMzVkZWcsIHJnYmEoNDcsIDExMSwgOTQsIC4xMCkg
MjUlLCB0cmFuc3BhcmVudCAyNSUpIDAgMC8yOHB4IDI4cHgsDQogICAgICAgICNmZmY7DQogICAg
ICBib3JkZXItYm90dG9tOiAxcHggc29saWQgdmFyKC0tbGluZSk7DQogICAgfQ0KDQogICAgLnBy
b2R1Y3QtYm9keSB7DQogICAgICBwYWRkaW5nOiAxNnB4Ow0KICAgIH0NCg0KICAgIC5wcm9kdWN0
IGgzIHsNCiAgICAgIG1hcmdpbjogMCAwIDZweDsNCiAgICAgIGZvbnQtc2l6ZTogMTdweDsNCiAg
ICB9DQoNCiAgICAucHJvZHVjdCBwIHsNCiAgICAgIG1hcmdpbjogMDsNCiAgICAgIGNvbG9yOiB2
YXIoLS1tdXRlZCk7DQogICAgICBmb250LXNpemU6IDE0cHg7DQogICAgfQ0KDQogICAgLmluZm8g
ew0KICAgICAgYmFja2dyb3VuZDogI2ZmZjsNCiAgICAgIGJvcmRlci10b3A6IDFweCBzb2xpZCB2
YXIoLS1saW5lKTsNCiAgICAgIGJvcmRlci1ib3R0b206IDFweCBzb2xpZCB2YXIoLS1saW5lKTsN
CiAgICB9DQoNCiAgICAuaW5mby1ib3ggew0KICAgICAgZGlzcGxheTogZ3JpZDsNCiAgICAgIGdy
aWQtdGVtcGxhdGUtY29sdW1uczogMWZyIDFmcjsNCiAgICAgIGdhcDogMjBweDsNCiAgICB9DQoN
CiAgICAubm90ZSB7DQogICAgICBiYWNrZ3JvdW5kOiB2YXIoLS1zb2Z0KTsNCiAgICAgIGJvcmRl
cjogMXB4IHNvbGlkICNkY2ViZTU7DQogICAgICBib3JkZXItcmFkaXVzOiAyMHB4Ow0KICAgICAg
cGFkZGluZzogMjRweDsNCiAgICB9DQoNCiAgICBmb290ZXIgew0KICAgICAgcGFkZGluZzogMzBw
eCAwOw0KICAgICAgY29sb3I6IHZhcigtLW11dGVkKTsNCiAgICAgIGZvbnQtc2l6ZTogMTRweDsN
CiAgICAgIGJvcmRlci10b3A6IDFweCBzb2xpZCB2YXIoLS1saW5lKTsNCiAgICB9DQoNCiAgICBA
bWVkaWEgKG1heC13aWR0aDogODQwcHgpIHsNCiAgICAgIC5oZXJvLA0KICAgICAgLmluZm8tYm94
IHsNCiAgICAgICAgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7DQogICAgICB9DQoNCiAgICAg
IC5ncmlkLA0KICAgICAgLnByb2R1Y3RzIHsNCiAgICAgICAgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5z
OiAxZnIgMWZyOw0KICAgICAgfQ0KDQogICAgICAuaGVybyB7DQogICAgICAgIHBhZGRpbmc6IDQ2
cHggMCA1OHB4Ow0KICAgICAgfQ0KICAgIH0NCg0KICAgIEBtZWRpYSAobWF4LXdpZHRoOiA1NjBw
eCkgew0KICAgICAgLnRvcGJhciB7DQogICAgICAgIGFsaWduLWl0ZW1zOiBmbGV4LXN0YXJ0Ow0K
ICAgICAgICBmbGV4LWRpcmVjdGlvbjogY29sdW1uOw0KICAgICAgfQ0KDQogICAgICBuYXYgew0K
ICAgICAgICBnYXA6IDEycHg7DQogICAgICB9DQoNCiAgICAgIC5ncmlkLA0KICAgICAgLnByb2R1
Y3RzLA0KICAgICAgLmJhZGdlLXJvdyB7DQogICAgICAgIGdyaWQtdGVtcGxhdGUtY29sdW1uczog
MWZyOw0KICAgICAgfQ0KDQogICAgICAudmlzdWFsIHsNCiAgICAgICAgcGFkZGluZzogMThweDsN
CiAgICAgIH0NCg0KICAgICAgLm1hdHRyZXNzIHsNCiAgICAgICAgaGVpZ2h0OiAyMTBweDsNCiAg
ICAgIH0NCiAgICB9DQogIDwvc3R5bGU+DQo8L2hlYWQ+DQo8Ym9keT4NCiAgPGhlYWRlcj4NCiAg
ICA8ZGl2IGNsYXNzPSJ3cmFwIj4NCiAgICAgIDxkaXYgY2xhc3M9InRvcGJhciI+DQogICAgICAg
IDxkaXYgY2xhc3M9ImxvZ28iPg0KICAgICAgICAgIDxkaXYgY2xhc3M9ImxvZ28tbWFyayI+Uzwv
ZGl2Pg0KICAgICAgICAgIDxzcGFuPtCh0L7QvdCc0LDRgNC60LXRgjwvc3Bhbj4NCiAgICAgICAg
PC9kaXY+DQogICAgICAgIDxuYXYgYXJpYS1sYWJlbD0i0J7RgdC90L7QstC90LDRjyDQvdCw0LLQ
uNCz0LDRhtC40Y8iPg0KICAgICAgICAgIDxhIGhyZWY9IiNjYXRhbG9nIj7QmtCw0YLQsNC70L7Q
szwvYT4NCiAgICAgICAgICA8YSBocmVmPSIjYmVuZWZpdHMiPtCf0L7QtNCx0L7RgDwvYT4NCiAg
ICAgICAgICA8YSBocmVmPSIjZGVsaXZlcnkiPtCU0L7RgdGC0LDQstC60LA8L2E+DQogICAgICAg
ICAgPGEgaHJlZj0iI2NvbnRhY3RzIj7QmtC+0L3RgtCw0LrRgtGLPC9hPg0KICAgICAgICA8L25h
dj4NCiAgICAgIDwvZGl2Pg0KDQogICAgICA8ZGl2IGNsYXNzPSJoZXJvIj4NCiAgICAgICAgPGRp
dj4NCiAgICAgICAgICA8aDE+0JzQsNGC0YDQsNGB0Ysg0Lgg0LDQutGB0LXRgdGB0YPQsNGA0Ysg
0LTQu9GPINGB0L/QvtC60L7QudC90L7Qs9C+INGB0L3QsDwvaDE+DQogICAgICAgICAgPHAgY2xh
c3M9ImxlYWQiPg0KICAgICAgICAgICAg0J/QvtC00LHQuNGA0LDQtdC8INC80LDRgtGA0LDRgdGL
LCDQv9C+0LTRg9GI0LrQuCDQuCDQt9Cw0YnQuNGC0L3Ri9C1INGH0LXRhdC70Ysg0L/QvtC0INC/
0YDQuNCy0YvRh9C60Lgg0YHQvdCwLCDRgNC+0YHRgiwg0LLQtdGBINC4INGD0YDQvtCy0LXQvdGM
INC20ZHRgdGC0LrQvtGB0YLQuC4NCiAgICAgICAgICAgINCg0LDQsdC+0YLQsNC10Lwg0YEg0LrQ
u9Cw0YHRgdC40YfQtdGB0LrQuNC80Lgg0Lgg0L7RgNGC0L7Qv9C10LTQuNGH0LXRgdC60LjQvNC4
INC80L7QtNC10LvRj9C80Lgg0LTQu9GPINC00L7QvNCwLCDQtNCw0YfQuCDQuCDQs9C+0YHRgtC1
0LLRi9GFINC60L7QvNC90LDRgi4NCiAgICAgICAgICA8L3A+DQogICAgICAgICAgPGRpdiBjbGFz
cz0iYWN0aW9ucyI+DQogICAgICAgICAgICA8YSBjbGFzcz0iYnRuIGJ0bi1wcmltYXJ5IiBocmVm
PSIjY2F0YWxvZyI+0KHQvNC+0YLRgNC10YLRjCDQv9C+0LTQsdC+0YDQutGDPC9hPg0KICAgICAg
ICAgICAgPGEgY2xhc3M9ImJ0biBidG4tZ2hvc3QiIGhyZWY9IiNiZW5lZml0cyI+0JrQsNC6INCy
0YvQsdGA0LDRgtGMINC80LDRgtGA0LDRgTwvYT4NCiAgICAgICAgICA8L2Rpdj4NCiAgICAgICAg
PC9kaXY+DQoNCiAgICAgICAgPGRpdiBjbGFzcz0idmlzdWFsIiBhcmlhLWhpZGRlbj0idHJ1ZSI+
DQogICAgICAgICAgPGRpdiBjbGFzcz0ibWF0dHJlc3MiPjwvZGl2Pg0KICAgICAgICAgIDxkaXYg
Y2xhc3M9ImJhZGdlLXJvdyI+DQogICAgICAgICAgICA8ZGl2IGNsYXNzPSJiYWRnZSI+0JPQsNGA
0LDQvdGC0LjRjzwvZGl2Pg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0iYmFkZ2UiPtCU0L7RgdGC
0LDQstC60LA8L2Rpdj4NCiAgICAgICAgICAgIDxkaXYgY2xhc3M9ImJhZGdlIj7Qn9C+0LTQsdC+
0YA8L2Rpdj4NCiAgICAgICAgICA8L2Rpdj4NCiAgICAgICAgPC9kaXY+DQogICAgICA8L2Rpdj4N
CiAgICA8L2Rpdj4NCiAgPC9oZWFkZXI+DQoNCiAgPG1haW4+DQogICAgPHNlY3Rpb24gaWQ9ImJl
bmVmaXRzIj4NCiAgICAgIDxkaXYgY2xhc3M9IndyYXAiPg0KICAgICAgICA8aDIgY2xhc3M9InNl
Y3Rpb24tdGl0bGUiPtCn0YLQviDRg9GH0LjRgtGL0LLQsNC10Lwg0L/RgNC4INC/0L7QtNCx0L7R
gNC1PC9oMj4NCiAgICAgICAgPHAgY2xhc3M9InNlY3Rpb24tdGV4dCI+DQogICAgICAgICAg0KXQ
vtGA0L7RiNC40Lkg0LzQsNGC0YDQsNGBINC00L7Qu9C20LXQvSDQv9C+0LTQtNC10YDQttC40LLQ
sNGC0Ywg0L/QvtC30LLQvtC90L7Rh9C90LjQuiwg0L3QtSDQv9GA0L7QstCw0LvQuNCy0LDRgtGM
0YHRjyDQv9C+0LQg0LLQtdGB0L7QvCDQuCDQv9C+0LTRhdC+0LTQuNGC0Ywg0L/QviDQttGR0YHR
gtC60L7RgdGC0LguDQogICAgICAgICAg0J3QuNC20LUg4oCUINC+0YHQvdC+0LLQvdGL0LUg0L/Q
sNGA0LDQvNC10YLRgNGLLCDQvdCwINC60L7RgtC+0YDRi9C1INGB0YLQvtC40YIg0YHQvNC+0YLR
gNC10YLRjCDQv9C10YDQtdC0INC/0L7QutGD0L/QutC+0LkuDQogICAgICAgIDwvcD4NCg0KICAg
ICAgICA8ZGl2IGNsYXNzPSJncmlkIj4NCiAgICAgICAgICA8YXJ0aWNsZSBjbGFzcz0iY2FyZCI+
DQogICAgICAgICAgICA8ZGl2IGNsYXNzPSJpY29uIj7imIE8L2Rpdj4NCiAgICAgICAgICAgIDxo
Mz7QltGR0YHRgtC60L7RgdGC0Yw8L2gzPg0KICAgICAgICAgICAgPHA+0JzRj9Cz0LrQuNC1LCDR
gdGA0LXQtNC90LjQtSDQuCDQttGR0YHRgtC60LjQtSDQvNC+0LTQtdC70Lgg0LTQu9GPINGA0LDQ
t9C90YvRhSDQv9GA0LjQstGL0YfQtdC6INGB0L3QsDog0L3QsCDQsdC+0LrRgywg0YHQv9C40L3Q
tSDQuNC70Lgg0LbQuNCy0L7RgtC1LjwvcD4NCiAgICAgICAgICA8L2FydGljbGU+DQogICAgICAg
ICAgPGFydGljbGUgY2xhc3M9ImNhcmQiPg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0iaWNvbiI+
4oyBPC9kaXY+DQogICAgICAgICAgICA8aDM+0J7RgdC90L7QstCw0L3QuNC1PC9oMz4NCiAgICAg
ICAgICAgIDxwPtCf0YDRg9C20LjQvdC90YvQtSDQuCDQsdC10YHQv9GA0YPQttC40L3QvdGL0LUg
0LLQsNGA0LjQsNC90YLRiyDRgSDRgNCw0LfQvdC+0Lkg0YHRgtC10L/QtdC90YzRjiDQv9C+0LTQ
tNC10YDQttC60Lgg0Lgg0YDQsNGB0L/RgNC10LTQtdC70LXQvdC40Y8g0L3QsNCz0YDRg9C30LrQ
uC48L3A+DQogICAgICAgICAgPC9hcnRpY2xlPg0KICAgICAgICAgIDxhcnRpY2xlIGNsYXNzPSJj
YXJkIj4NCiAgICAgICAgICAgIDxkaXYgY2xhc3M9Imljb24iPuKckzwvZGl2Pg0KICAgICAgICAg
ICAgPGgzPtCg0LDQt9C80LXRgDwvaDM+DQogICAgICAgICAgICA8cD7QntC00L3QvtGB0L/QsNC7
0YzQvdGL0LUsINC/0L7Qu9GD0YLQvtGA0L3Ri9C1LCDQtNCy0YPRgdC/0LDQu9GM0L3Ri9C1INC4
INC90LXRgdGC0LDQvdC00LDRgNGC0L3Ri9C1INGA0LDQt9C80LXRgNGLINC/0L7QtCDQutC+0L3Q
utGA0LXRgtC90YPRjiDQutGA0L7QstCw0YLRjC48L3A+DQogICAgICAgICAgPC9hcnRpY2xlPg0K
ICAgICAgICA8L2Rpdj4NCiAgICAgIDwvZGl2Pg0KICAgIDwvc2VjdGlvbj4NCg0KICAgIDxzZWN0
aW9uIGlkPSJjYXRhbG9nIiBjbGFzcz0iaW5mbyI+DQogICAgICA8ZGl2IGNsYXNzPSJ3cmFwIj4N
CiAgICAgICAgPGgyIGNsYXNzPSJzZWN0aW9uLXRpdGxlIj7Qn9C+0L/Rg9C70Y/RgNC90YvQtSDQ
utCw0YLQtdCz0L7RgNC40Lg8L2gyPg0KICAgICAgICA8cCBjbGFzcz0ic2VjdGlvbi10ZXh0Ij4N
CiAgICAgICAgICDQodGC0YDQsNC90LjRhtCwINC90L7RgdC40YIg0LjQvdGE0L7RgNC80LDRhtC4
0L7QvdC90YvQuSDRhdCw0YDQsNC60YLQtdGALiDQkNGB0YHQvtGA0YLQuNC80LXQvdGCINC4INC9
0LDQu9C40YfQuNC1INGC0L7QstCw0YDQvtCyINGD0YLQvtGH0L3Rj9GO0YLRgdGPINGDINC80LXQ
vdC10LTQttC10YDQsC4NCiAgICAgICAgPC9wPg0KDQogICAgICAgIDxkaXYgY2xhc3M9ImdyaWQg
cHJvZHVjdHMiPg0KICAgICAgICAgIDxhcnRpY2xlIGNsYXNzPSJwcm9kdWN0Ij4NCiAgICAgICAg
ICAgIDxkaXYgY2xhc3M9InByb2R1Y3QtaW1nIj48L2Rpdj4NCiAgICAgICAgICAgIDxkaXYgY2xh
c3M9InByb2R1Y3QtYm9keSI+DQogICAgICAgICAgICAgIDxoMz7QntGA0YLQvtC/0LXQtNC40YfQ
tdGB0LrQuNC1INC80LDRgtGA0LDRgdGLPC9oMz4NCiAgICAgICAgICAgICAgPHA+0JTQu9GPINC1
0LbQtdC00L3QtdCy0L3QvtCz0L4g0YHQvdCwINC4INGB0YLQsNCx0LjQu9GM0L3QvtC5INC/0L7Q
tNC00LXRgNC20LrQuC48L3A+DQogICAgICAgICAgICA8L2Rpdj4NCiAgICAgICAgICA8L2FydGlj
bGU+DQogICAgICAgICAgPGFydGljbGUgY2xhc3M9InByb2R1Y3QiPg0KICAgICAgICAgICAgPGRp
diBjbGFzcz0icHJvZHVjdC1pbWciPjwvZGl2Pg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJv
ZHVjdC1ib2R5Ij4NCiAgICAgICAgICAgICAgPGgzPtCi0L7QvdC60LjQtSDRgtC+0L/Qv9C10YDR
izwvaDM+DQogICAgICAgICAgICAgIDxwPtCU0LvRjyDQtNC40LLQsNC90L7Qsiwg0LPQvtGB0YLQ
tdCy0YvRhSDQvNC10YHRgiDQuCDRgNC10LPRg9C70LjRgNC+0LLQutC4INC20ZHRgdGC0LrQvtGB
0YLQuC48L3A+DQogICAgICAgICAgICA8L2Rpdj4NCiAgICAgICAgICA8L2FydGljbGU+DQogICAg
ICAgICAgPGFydGljbGUgY2xhc3M9InByb2R1Y3QiPg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0i
cHJvZHVjdC1pbWciPjwvZGl2Pg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJvZHVjdC1ib2R5
Ij4NCiAgICAgICAgICAgICAgPGgzPtCf0L7QtNGD0YjQutC4PC9oMz4NCiAgICAgICAgICAgICAg
PHA+0JDQvdCw0YLQvtC80LjRh9C10YHQutC40LUg0Lgg0LrQu9Cw0YHRgdC40YfQtdGB0LrQuNC1
INC80L7QtNC10LvQuC48L3A+DQogICAgICAgICAgICA8L2Rpdj4NCiAgICAgICAgICA8L2FydGlj
bGU+DQogICAgICAgICAgPGFydGljbGUgY2xhc3M9InByb2R1Y3QiPg0KICAgICAgICAgICAgPGRp
diBjbGFzcz0icHJvZHVjdC1pbWciPjwvZGl2Pg0KICAgICAgICAgICAgPGRpdiBjbGFzcz0icHJv
ZHVjdC1ib2R5Ij4NCiAgICAgICAgICAgICAgPGgzPtCn0LXRhdC70Ysg0Lgg0L3QsNC80LDRgtGA
0LDRgdC90LjQutC4PC9oMz4NCiAgICAgICAgICAgICAgPHA+0JfQsNGJ0LjRgtCwINC80LDRgtGA
0LDRgdCwINC+0YIg0LLQu9Cw0LPQuCwg0L/Ri9C70Lgg0Lgg0LjQt9C90L7RgdCwLjwvcD4NCiAg
ICAgICAgICAgIDwvZGl2Pg0KICAgICAgICAgIDwvYXJ0aWNsZT4NCiAgICAgICAgPC9kaXY+DQog
ICAgICA8L2Rpdj4NCiAgICA8L3NlY3Rpb24+DQoNCiAgICA8c2VjdGlvbiBpZD0iZGVsaXZlcnki
Pg0KICAgICAgPGRpdiBjbGFzcz0id3JhcCBpbmZvLWJveCI+DQogICAgICAgIDxkaXYgY2xhc3M9
Im5vdGUiPg0KICAgICAgICAgIDxoMiBjbGFzcz0ic2VjdGlvbi10aXRsZSI+0JTQvtGB0YLQsNCy
0LrQsDwvaDI+DQogICAgICAgICAgPHAgY2xhc3M9InNlY3Rpb24tdGV4dCI+DQogICAgICAgICAg
ICDQktC+0LfQvNC+0LbQvdCwINC00L7RgdGC0LDQstC60LAg0L/QviDQs9C+0YDQvtC00YMg0Lgg
0L7QsdC70LDRgdGC0LguINCj0YHQu9C+0LLQuNGPINC30LDQstC40YHRj9GCINC+0YIg0YDQsNC3
0LzQtdGA0LAg0LjQt9C00LXQu9C40Y8sINCw0LTRgNC10YHQsCDQuCDQstGL0LHRgNCw0L3QvdC+
0LPQviDRgdC/0L7RgdC+0LHQsCDQv9C+0LTRitGR0LzQsC4NCiAgICAgICAgICA8L3A+DQogICAg
ICAgIDwvZGl2Pg0KICAgICAgICA8ZGl2IGNsYXNzPSJub3RlIj4NCiAgICAgICAgICA8aDIgY2xh
c3M9InNlY3Rpb24tdGl0bGUiPtCa0L7QvdGB0YPQu9GM0YLQsNGG0LjRjzwvaDI+DQogICAgICAg
ICAgPHAgY2xhc3M9InNlY3Rpb24tdGV4dCI+DQogICAgICAgICAgICDQlNC70Y8g0L/QvtC00LHQ
vtGA0LAg0L7QsdGL0YfQvdC+INC90YPQttC90Ysg0YDQsNC30LzQtdGAINC60YDQvtCy0LDRgtC4
LCDQttC10LvQsNC10LzQsNGPINC20ZHRgdGC0LrQvtGB0YLRjCwg0LLQtdGBINGB0L/Rj9GJ0LjR
hSDQuCDQv9GA0LXQtNC/0L7Rh9GC0LXQvdC40Y8g0L/QviDQvNCw0YLQtdGA0LjQsNC70LDQvC4N
CiAgICAgICAgICA8L3A+DQogICAgICAgIDwvZGl2Pg0KICAgICAgPC9kaXY+DQogICAgPC9zZWN0
aW9uPg0KICA8L21haW4+DQoNCiAgPGZvb3RlciBpZD0iY29udGFjdHMiPg0KICAgIDxkaXYgY2xh
c3M9IndyYXAiPg0KICAgICAgwqkgPHNwYW4gaWQ9InllYXIiPjwvc3Bhbj4g0KHQvtC90JzQsNGA
0LrQtdGCLiDQmNC90YTQvtGA0LzQsNGG0LjQvtC90L3QsNGPINGB0YLRgNCw0L3QuNGG0LAuDQog
ICAgPC9kaXY+DQogIDwvZm9vdGVyPg0KDQogIDxzY3JpcHQ+DQogICAgZG9jdW1lbnQuZ2V0RWxl
bWVudEJ5SWQoInllYXIiKS50ZXh0Q29udGVudCA9IG5ldyBEYXRlKCkuZ2V0RnVsbFllYXIoKTsN
CiAgPC9zY3JpcHQ+DQo8L2JvZHk+DQo8L2h0bWw+DQo=
EOF

cat > "$PROJECT_DIR/docker-compose.yaml" <<'EOF'
services:
  xray:
    image: ghcr.io/xtls/xray-core:latest
    container_name: vpnforge-xray
    restart: unless-stopped
    ports:
      - "443:443"
      - "8443:8443"
    volumes:
      - ./xray/config.json:/usr/local/etc/xray/config.json:ro
      - /var/lib/xray/cert:/etc/xray/cert:ro
    ulimits:
      nofile:
        soft: 65535
        hard: 65535

  nginx:
    image: nginx:alpine
    container_name: vpnforge-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/html:/usr/share/nginx/html:ro
      - ./letsencrypt:/etc/letsencrypt:ro

  certbot:
    image: certbot/certbot:latest
    container_name: vpnforge-certbot
    volumes:
      - ./nginx/html:/var/www/html
      - ./letsencrypt:/etc/letsencrypt
      - ./letsencrypt-lib:/var/lib/letsencrypt
EOF

cd "$PROJECT_DIR"

[[ $EUID -eq 0 ]] || { echo -e "${RED}Root privileges required.${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is not installed.${NC}"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo -e "${RED}Docker Compose plugin is not installed.${NC}"; exit 1; }

DOMAIN="$(echo "$1" | xargs)"

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Domain is not set.${NC}"
    echo "Usage: ./init.sh your-domain.com"
    exit 1
fi

LOCAL_IP=$(hostname -I | awk '{print $1}')
if command -v dig >/dev/null 2>&1; then
    DNS_IP=$(dig +short "$DOMAIN" | grep '^[0-9]' | head -n 1)
elif command -v getent >/dev/null 2>&1; then
    DNS_IP=$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}')
else
    DNS_IP=""
fi

if [ -n "$DNS_IP" ] && [ "$LOCAL_IP" != "$DNS_IP" ]; then
    echo -e "${RED}Warning: local IP ($LOCAL_IP) does not match $DOMAIN A-record ($DNS_IP).${NC}"
    echo -e "${YEL}Set one A-record for the domain to $LOCAL_IP.${NC}"
    read -p "Continue at your own risk? (y/N): " choice

    if [[ ! "$choice" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
fi

bbr=$(sysctl -a 2>/dev/null | grep net.ipv4.tcp_congestion_control || true)
if [ "$bbr" = "net.ipv4.tcp_congestion_control = bbr" ]; then
    echo -e "${GRN}BBR already enabled.${NC}"
else
    echo "net.core.default_qdisc=fq" > /etc/sysctl.d/999-autoXRAY.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/999-autoXRAY.conf
    sysctl --system
    echo -e "${GRN}BBR enabled.${NC}"
fi

cat > "$CONFIG_PATH" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
        allow all;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

docker compose up -d nginx

if docker compose run --rm certbot certonly \
    --webroot \
    -w /var/www/html \
    -d "$DOMAIN" \
    -m "mail@$DOMAIN" \
    --agree-tos \
    --non-interactive; then
    mkdir -p "$CERT_DIR"
    cp -L "$LE_DIR/live/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
    cp -L "$LE_DIR/live/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
    chmod 644 "$CERT_DIR/fullchain.pem"
    chmod 644 "$CERT_DIR/privkey.pem"
    echo -e "${GRN}Let's Encrypt certificate received.${NC}"
else
    ret=$?
    echo -e "${RED}Certbot failed. Exit code: $ret${NC}"
    exit "$ret"
fi

path_xhttp="$(gen_path)"
path_subpage="$(gen_token 20)"
fpBro="$FINGERPRINT"

xray_uuid_vrv="$(cat /proc/sys/kernel/random/uuid)"
key_output="$(docker run --rm ghcr.io/xtls/xray-core:latest x25519)"
xray_privateKey_vrv="$(echo "$key_output" | awk -F': ' 'tolower($1) ~ /private/ {print $2}')"
xray_publicKey_vrv="$(echo "$key_output" | awk -F': ' 'tolower($1) ~ /public|password/ {print $2}')"
xray_shortIds_vrv="$(openssl rand -hex 8)"

if [ -z "$xray_privateKey_vrv" ] || [ -z "$xray_publicKey_vrv" ]; then
    echo -e "${RED}Failed to generate Xray x25519 keys.${NC}"
    exit 1
fi

cat > "$CONFIG_PATH" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
        allow all;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    server_name $DOMAIN;
    listen 8080 ssl proxy_protocol;
    listen 8081 proxy_protocol;
    listen 8082 proxy_protocol;
    http2 on;

    set_real_ip_from 172.16.0.0/12;
    set_real_ip_from 192.168.0.0/16;
    set_real_ip_from 10.0.0.0/8;
    real_ip_header proxy_protocol;

    root /usr/share/nginx/html;
    index index.html;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:MozSSL:10m;
    ssl_session_tickets off;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    grpc_read_timeout 1h;
    grpc_send_timeout 1h;
    grpc_set_header X-Real-IP \$remote_addr;
    resolver 127.0.0.11 valid=30s ipv6=off;

    location = /${path_subpage}.txt {
        types { }
        default_type text/plain;
        charset utf-8;
        add_header profile-title "base64:YXV0b1hSQVk=";
        try_files \$uri =404;
    }

    location /${path_xhttp} {
        set \$xray_http xray:8400;
        proxy_pass http://\$xray_http;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /${path_xhttp}11 {
        if (\$request_method != "POST") {
            return 404;
        }

        client_body_buffer_size 1m;
        client_body_timeout 1h;
        client_max_body_size 0;
        set \$xray_grpc xray:8411;
        grpc_pass grpc://\$xray_grpc;
    }

    location ~ /\\.ht {
        deny all;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

cat > "$XRAY_CONFIG_PATH" <<EOF
{
  "log": {
    "dnsLog": false,
    "access": "/dev/stdout",
    "error": "/dev/stderr",
    "loglevel": "none"
  },
  "dns": {
    "servers": [
      "https+local://8.8.4.4/dns-query",
      "https+local://8.8.8.8/dns-query",
      "https+local://1.1.1.1/dns-query",
      "localhost"
    ],
    "queryStrategy": "UseIPv4"
  },
  "inbounds": [
    {
      "tag": "vsRAWrtyVISION",
      "port": 443,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "flow": "xtls-rprx-vision",
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none",
        "fallbacks": [
          {
            "dest": "3333",
            "xver": 2
          }
        ]
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      },
      "streamSettings": {
        "network": "raw",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "xver": 2,
          "target": "nginx:8080",
          "spiderX": "/",
          "shortIds": ["${xray_shortIds_vrv}"],
          "privateKey": "${xray_privateKey_vrv}",
          "serverNames": ["$DOMAIN"],
          "limitFallbackUpload": {
            "afterBytes": 0,
            "bytesPerSec": 65536,
            "burstBytesPerSec": 0
          },
          "limitFallbackDownload": {
            "afterBytes": 5242880,
            "bytesPerSec": 262144,
            "burstBytesPerSec": 2097152
          }
        }
      }
    },
    {
      "tag": "vsXHTTPrty",
      "port": 3333,
      "listen": "127.0.0.1",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "mode": "stream-one",
          "path": "/${path_xhttp}"
        },
        "security": "none",
        "sockopt": {
          "acceptProxyProtocol": true
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsRAWtlsVISION",
      "port": 8443,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "flow": "xtls-rprx-vision",
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none",
        "fallbacks": [
          {
            "path": "/${path_xhttp}22",
            "dest": "@vless-ws",
            "xver": 2
          },
          {
            "alpn": "h2",
            "dest": "nginx:8082",
            "xver": 2
          },
          {
            "dest": "nginx:8081",
            "xver": 2
          }
        ]
      },
      "streamSettings": {
        "network": "raw",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/xray/cert/fullchain.pem",
              "keyFile": "/etc/xray/cert/privkey.pem"
            }
          ],
          "minVersion": "1.2",
          "cipherSuites": "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
          "alpn": ["h2", "http/1.1"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsXHTTPtls",
      "port": 8400,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "mode": "auto",
          "path": "/${path_xhttp}"
        },
        "security": "none",
        "sockopt": {
          "acceptProxyProtocol": false
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsGRPCtls",
      "port": 8411,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "grpc",
        "grpcSettings": {
          "serviceName": "${path_xhttp}11"
        },
        "security": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "listen": "@vless-ws",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {
          "acceptProxyProtocol": true,
          "path": "/${path_xhttp}22"
        },
        "security": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "ForceIPv4"
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole"
    }
  ]
}
EOF

echo -e "${GRN}Nginx config created: $CONFIG_PATH${NC}"
echo -e "${GRN}Xray config created: $XRAY_CONFIG_PATH${NC}"

linkRTY1="vless://${xray_uuid_vrv}@$DOMAIN:443?security=reality&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni=$DOMAIN&fp=$fpBro&pbk=${xray_publicKey_vrv}&sid=${xray_shortIds_vrv}&spx=%2F#vlessRAWrealityVISION-autoXRAY"
linkRTY2="vless://${xray_uuid_vrv}@$DOMAIN:443?security=reality&type=xhttp&headerType=&path=%2F$path_xhttp&host=&mode=stream-one&extra=%7B%22xmux%22%3A%7B%22cMaxReuseTimes%22%3A%221000-3000%22%2C%22maxConcurrency%22%3A%223-5%22%2C%22maxConnections%22%3A0%2C%22hKeepAlivePeriod%22%3A0%2C%22hMaxRequestTimes%22%3A%22400-700%22%2C%22hMaxReusableSecs%22%3A%221200-1800%22%7D%2C%22headers%22%3A%7B%7D%2C%22noGRPCHeader%22%3Afalse%2C%22xPaddingBytes%22%3A%22400-800%22%2C%22scMaxEachPostBytes%22%3A1500000%2C%22scMinPostsIntervalMs%22%3A20%2C%22scStreamUpServerSecs%22%3A%2260-240%22%7D&sni=$DOMAIN&fp=$fpBro&pbk=${xray_publicKey_vrv}&sid=${xray_shortIds_vrv}&spx=%2F#vlessXHTTPrealityEXTRA-autoXRAY"
linkTLS1="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessRAWtlsVision-autoXRAY"
linkTLS2="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=xhttp&headerType=&path=%2F${path_xhttp}&host=&mode=auto&extra=%7B%22xmux%22%3A%7B%22cMaxReuseTimes%22%3A%221000-3000%22%2C%22maxConcurrency%22%3A%223-5%22%2C%22maxConnections%22%3A0%2C%22hKeepAlivePeriod%22%3A0%2C%22hMaxRequestTimes%22%3A%22400-700%22%2C%22hMaxReusableSecs%22%3A%221200-1800%22%7D%2C%22headers%22%3A%7B%7D%2C%22noGRPCHeader%22%3Afalse%2C%22xPaddingBytes%22%3A%22400-800%22%2C%22scMaxEachPostBytes%22%3A1500000%2C%22scMinPostsIntervalMs%22%3A20%2C%22scStreamUpServerSecs%22%3A%2260-240%22%7D&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessXHTTPtls-autoXRAY"
linkTLS3="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=ws&headerType=&path=%2F${path_xhttp}22&host=&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessWStls-autoXRAY"
linkTLS4="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=grpc&headerType=&serviceName=${path_xhttp}11&host=&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessGRPCtls-autoXRAY"

subPageTxtLink="https://$DOMAIN/$path_subpage.txt"
configListLink="https://$DOMAIN/$path_subpage.html"

CONFIGS_ARRAY=(
    "VLESS XHTTP REALITY EXTRA|$linkRTY2"
    "VLESS RAW REALITY VISION|$linkRTY1"
    "VLESS RAW TLS VISION|$linkTLS1"
    "VLESS XHTTP TLS EXTRA|$linkTLS2"
    "VLESS WS TLS|$linkTLS3"
    "VLESS GRPC TLS|$linkTLS4"
)

: > "$HTML_DIR/$path_subpage.txt"
for item in "${CONFIGS_ARRAY[@]}"; do
    printf '%s\n' "${item#*|}" >> "$HTML_DIR/$path_subpage.txt"
done

cat > "$HTML_DIR/$path_subpage.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>VPNForge configs</title>
<style>
body{font-family:monospace;background:#121212;color:#e0e0e0;padding:10px;max-width:900px;margin:0 auto}
h2{color:#c3e88d;border-top:2px solid #333;padding-top:20px;margin:15px 0 10px;font-size:18px}
.row{background:#1e1e1e;border:1px solid #333;border-radius:6px;padding:8px;display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
.label{background:#2c2c2c;color:#82aaff;padding:6px 10px;border-radius:4px;font-weight:700;font-size:13px;min-width:180px;text-align:center}
.code{flex:1;white-space:nowrap;overflow-x:auto;padding:8px;background:#121212;border-radius:4px;color:#c3e88d;font-size:12px}
button,a.btn{background:#333;color:#e0e0e0;border:1px solid #555;padding:7px 12px;border-radius:4px;cursor:pointer;font-weight:700;text-decoration:none}
button:hover,a.btn:hover{background:#c3e88d;color:#121212;border-color:#c3e88d}
@media(max-width:600px){.label,.code{width:100%;min-width:100%}button,a.btn{flex:1}}
</style>
<script>
function copyText(id,btn){navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{let t=btn.innerText;btn.innerText="OK";setTimeout(()=>btn.innerText=t,1200)})}
</script>
</head>
<body>
EOF

cat >> "$HTML_DIR/$path_subpage.html" <<EOF
<h2>TXT subscription</h2>
<div class="row">
  <div class="label">Subscription</div>
  <div class="code" id="subTxt">$subPageTxtLink</div>
  <button onclick="copyText('subTxt',this)">Copy</button>
  <a class="btn" href="happ://add/$subPageTxtLink">Add to HAPP</a>
</div>

<h2>Configs</h2>
EOF

idx=1
for item in "${CONFIGS_ARRAY[@]}"; do
    title="${item%%|*}"
    link="${item#*|}"
    cat >> "$HTML_DIR/$path_subpage.html" <<EOF
<div class="row">
  <div class="label">$title</div>
  <div class="code" id="c$idx">$link</div>
  <button onclick="copyText('c$idx',this)">Copy</button>
</div>
EOF
    ((idx++))
done

cat >> "$HTML_DIR/$path_subpage.html" <<'EOF'
</body>
</html>
EOF

docker compose up -d nginx xray
docker compose exec -T nginx nginx -s reload

is_container_running() {
    local service="$1"
    local cid

    cid="$(docker compose ps -q "$service" 2>/dev/null)"
    [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = "true" ]
}

echo -e "\n${YEL}=== Final status ===${NC}"

if is_container_running "nginx"; then
    echo -e "Nginx container: ${GRN}RUNNING${NC}"
    if docker compose exec -T nginx nginx -t >/dev/null 2>&1; then
        echo -e "Nginx config: ${GRN}OK${NC}"
    else
        echo -e "Nginx config: ${RED}ERROR${NC}"
        echo "Check: docker compose logs nginx"
    fi
else
    echo -e "Nginx container: ${RED}STOPPED/ERROR${NC}"
    echo "Check: docker compose logs nginx"
fi

if is_container_running "xray"; then
    echo -e "Xray container: ${GRN}RUNNING${NC}"
else
    echo -e "Xray container: ${RED}STOPPED/ERROR${NC}"
    echo "Check: docker compose logs xray"
fi

if [ -f "$HTML_DIR/$path_subpage.txt" ]; then
    echo -e "TXT subscription file: ${GRN}OK${NC}"
else
    echo -e "TXT subscription file: ${RED}NOT FOUND${NC}"
fi

if [ -f "$HTML_DIR/$path_subpage.html" ]; then
    echo -e "HTML config page: ${GRN}OK${NC}"
else
    echo -e "HTML config page: ${RED}NOT FOUND${NC}"
fi

if is_container_running "xray" && docker compose exec -T xray test -r /etc/xray/cert/fullchain.pem && docker compose exec -T xray test -r /etc/xray/cert/privkey.pem; then
    echo -e "Xray certificates: ${GRN}OK${NC}"
else
    echo -e "Xray certificates: ${RED}NOT FOUND/NOT READABLE${NC}"
fi

echo -e "
${YEL}VLESS XHTTP REALITY EXTRA${NC}
$linkRTY2

${YEL}VLESS RAW REALITY VISION${NC}
$linkRTY1

${YEL}VLESS RAW TLS VISION${NC}
$linkTLS1

${YEL}VLESS XHTTP TLS EXTRA${NC}
$linkTLS2

${YEL}VLESS WS TLS${NC}
$linkTLS3

${YEL}VLESS GRPC TLS${NC}
$linkTLS4

${YEL}TXT subscription${NC}
$subPageTxtLink

${YEL}Saved configs page${NC}
${GRN}$configListLink${NC}

${YEL}Docker logs:${NC}
docker compose logs nginx
docker compose logs xray
"
