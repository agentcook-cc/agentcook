import type { Metric } from "web-vitals";
import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";

export interface VitalSample extends Metric {
  surface: "app" | "admin";
}

export type MetricReporter = (sample: VitalSample) => void;

interface InstallOptions {
  surface: "app" | "admin";
  reporter?: MetricReporter;
}

const DEFAULT_REPORTER: MetricReporter = (sample) => {
  const { surface, name, value, rating, id, delta, navigationType } = sample;
  // eslint-disable-next-line no-console
  console.log("[web-vitals]", {
    surface,
    name,
    value: Math.round(value * 1000) / 1000,
    rating,
    delta: Math.round(delta * 1000) / 1000,
    id,
    navigationType,
  });
};

export function installWebVitals({
  surface,
  reporter = DEFAULT_REPORTER,
}: InstallOptions): void {
  const tag = (metric: Metric) =>
    reporter({ ...metric, surface } as VitalSample);
  onCLS(tag);
  onFCP(tag);
  onINP(tag);
  onLCP(tag);
  onTTFB(tag);
}
