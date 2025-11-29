#!/bin/bash

# fetch_lstrm_rlt.py 실행을 위한 환경 설정 및 실행 스크립트

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

echo -e "${GREEN}=== Legal Translator - fetch_lstrm_rlt 실행 스크립트 ===${NC}"

# 1. 가상환경 확인 및 생성
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[1/5] 가상환경 생성 중...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ 가상환경 생성 완료: $VENV_DIR${NC}"
else
    echo -e "${GREEN}[1/5] 가상환경이 이미 존재합니다: $VENV_DIR${NC}"
fi

# 2. 가상환경 활성화
    echo -e "${YELLOW}[2/5] 가상환경 활성화 중...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ 가상환경 활성화 완료${NC}"

# 3. pip 업그레이드
    echo -e "${YELLOW}[3/5] pip 업그레이드 중...${NC}"
"$VENV_PIP" install --upgrade pip -q
echo -e "${GREEN}✓ pip 업그레이드 완료${NC}"

# 4. requirements.txt 설치
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}[4/5] requirements.txt 설치 중...${NC}"
    "$VENV_PIP" install -r "$PROJECT_ROOT/requirements.txt"
    echo -e "${GREEN}✓ requirements.txt 설치 완료${NC}"
else
    echo -e "${RED}✗ requirements.txt를 찾을 수 없습니다: $PROJECT_ROOT/requirements.txt${NC}"
    exit 1
fi

# 5. .env 파일에서 환경변수 로드
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}[5/5] .env 파일에서 환경변수 로드 중...${NC}"
    # .env 파일을 읽어서 환경변수로 export (주석과 빈 줄 제외)
    while IFS= read -r line || [ -n "$line" ]; do
        # 주석과 빈 줄 건너뛰기
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^# ]] && continue
        # KEY=VALUE 형태인지 확인
        if [[ "$line" =~ ^[[:alnum:]_]+= ]]; then
            # 따옴표 제거 및 export
            key=$(echo "$line" | cut -d'=' -f1 | xargs)
            value=$(echo "$line" | cut -d'=' -f2- | sed -e "s/^[[:space:]]*['\"]//" -e "s/['\"][[:space:]]*$//" | xargs)
            if [ -n "$key" ]; then
                export "$key=$value"
            fi
        fi
    done < "$ENV_FILE"
    echo -e "${GREEN}✓ .env 파일 로드 완료${NC}"
fi

# 6. 환경변수 확인
if [ -z "$LAWGO_OC" ]; then
    echo -e "${YELLOW}⚠ LAWGO_OC 환경변수가 설정되지 않았습니다.${NC}"
    echo -e "${YELLOW}  .env 파일에 LAWGO_OC=your_api_key 형태로 추가하세요.${NC}"
    echo ""
    read -p "LAWGO_OC를 지금 입력하시겠습니까? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "LAWGO_OC 값을 입력하세요: " LAWGO_OC
        export LAWGO_OC
        echo -e "${GREEN}✓ LAWGO_OC 환경변수 설정 완료${NC}"
    else
        echo -e "${RED}✗ LAWGO_OC 환경변수가 필요합니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ LAWGO_OC 환경변수 확인됨${NC}"
fi

# 7. 스크립트 실행
echo ""
echo -e "${GREEN}=== fetch_lstrm_rlt.py 실행 ===${NC}"
echo -e "${YELLOW}사용 가능한 명령어:${NC}"
echo -e "  1) 법령용어 목록 수집:"
echo -e "     ${GREEN}python3 scripts/fetch_lstrm_rlt.py lstrm --out-dir data --sleep 0.3 --timeout 3 6${NC}"
echo -e "  2) 일상용어 연계 수집:"
echo -e "     ${GREEN}python3 scripts/fetch_lstrm_rlt.py relations --out-dir data --resume --sleep 0.1 --timeout 3 6${NC}"
echo ""

# 명령행 인자가 있으면 실행, 없으면 사용법 표시
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}사용 예시:${NC}"
    echo -e "  ${GREEN}./run_fetch_lstrm.sh lstrm --out-dir data --sleep 0.3 --timeout 3 6${NC}"
    echo -e "  ${GREEN}./run_fetch_lstrm.sh relations --out-dir data --resume --sleep 0.1 --timeout 3 6${NC}"
    echo ""
    echo -e "${YELLOW}또는 직접 실행:${NC}"
    echo -e "  ${GREEN}source venv/bin/activate${NC}"
    echo -e "  ${GREEN}python3 scripts/fetch_lstrm_rlt.py [command] [options]${NC}"
else
    # 인자가 있으면 스크립트 실행
    "$VENV_PYTHON" "$PROJECT_ROOT/scripts/fetch_lstrm_rlt.py" "$@"
fi
