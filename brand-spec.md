# Brand Spec: 전원마을 파인더

## Product Position

- Product: 전원마을 파인더
- Literal offer: 지금 분양 가능한 전원마을을 공공데이터 근거와 함께 찾는 서비스
- Primary audience: 귀농·귀촌을 검토하며 실제 입주 가능 후보를 빠르게 좁히려는 사람
- Voice: 차분하고 구체적이며 과장하지 않는다. 추천보다 확인, 확신보다 근거를 말한다.
- Active design-system source: project-local tokens in `app/frontend/style.css`, distilled from Impeccable design principles.

## Source Evidence

- Product source: `README.md`, `MVP제안서.md`, `spec.md`
- Repository: https://github.com/Aithor-organization/krc-jeonwonmaeul-finder
- Public-data identifiers: KRC 전원마을 분양정보 `15104395`, 농촌마을현황 `15104291`, 논가뭄지도 `15117185`
- Runtime truth: `/api/health` determines whether the page labels the experience as sample mode.

## Visual Direction

**Grounded civic editorial**: Korean rural landscape photography, public-service clarity, and restrained editorial typography. The page should feel useful before it feels promotional.

- Hero: full-bleed rural landscape with direct product search over the image
- Layout: left-aligned, asymmetric, strong horizontal rules, unframed information bands
- Shape: 8px maximum radius for controls and cards; pills only for status and query suggestions
- Motion: short state transitions only; no decorative floating motion
- Elevation: borders first, one low shadow level for result cards and the dialog

## Tokens

- Ink: `#101914`
- Forest: `#1f5a40`
- Forest dark: `#123b2a`
- Signal orange: `#f26a3d`
- Paper: `#f4f6f1`
- White: `#ffffff`
- Muted text: `#5f6c64`
- Border: `#d7ddd7`
- Display typography: `MaruBuri`, `Nanum Myeongjo`, Georgia, serif
- Body typography: `Pretendard`, `Noto Sans KR`, `Apple SD Gothic Neo`, `Malgun Gothic`, sans-serif

## Assets

- Hero photograph: `app/frontend/assets/hero-rural-village.jpg`
- Provenance: generated for this project with the built-in OpenAI image generation tool
- Prompt intent: photorealistic South Korean rural settlement, restrained morning light, darker left-side copy space, no logos or text
- Logo treatment: product-name wordmark paired with the Lucide `map-pin` icon; never imply an official KRC logo or endorsement

## Forbidden Moves

- Do not claim that sample data is live data.
- Do not imply that a ranking guarantees a contract, investment result, or local water conditions.
- Do not invent usage numbers, testimonials, awards, or official partnerships.
- Do not use purple/blue gradients, glass cards, decorative blobs, or oversized pill buttons.
- Do not hide evidence, warnings, data dates, or the final-confirmation disclaimer.
- Do not use generic stock photos of staged people or luxury country homes.
