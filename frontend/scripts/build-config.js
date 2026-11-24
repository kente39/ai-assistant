// Vercel 빌드 시 환경 변수 → public/config.js 생성
// 바닐라 JS는 브라우저에서 process.env를 읽을 수 없으므로 빌드 단계에서 주입한다.
// (API 주소는 공개돼도 되는 값. 비밀 키는 절대 프론트에 넣지 않는다.)
const fs = require("fs");
const path = require("path");

const config = {
  API_BASE_URL: process.env.API_BASE_URL || "http://localhost:8000",
  DATA_NAME: process.env.DATA_NAME || "일별 매출",
  DATA_UNIT: process.env.DATA_UNIT || "원",
};
const out = path.join(__dirname, "..", "public", "config.js");
fs.writeFileSync(out, `window.APP_CONFIG = ${JSON.stringify(config, null, 2)};\n`);
console.log("config.js generated:", config);
