// Fixture 2/5: template literal codename. Expected to FAIL ESLint
// (no-restricted-syntax TemplateElement selector).

const env = "prod";
export const queueLabel = `Pandora-${env}-queue`;
