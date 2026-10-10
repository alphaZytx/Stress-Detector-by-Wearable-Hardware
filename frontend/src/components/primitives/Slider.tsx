import * as RSlider from "@radix-ui/react-slider";

export function Slider({
  value,
  onValueChange,
  min = 0,
  max = 1,
  step = 0.05,
  label,
}: {
  value: number;
  onValueChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
}) {
  return (
    <RSlider.Root
      className="relative flex h-5 w-full touch-none select-none items-center"
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={(v) => onValueChange(v[0])}
      aria-label={label}
    >
      <RSlider.Track className="relative h-2.5 w-full grow rounded-none border-2 border-clinical-border bg-clinical-surface-2">
        <RSlider.Range className="absolute h-full bg-clinical-accent" />
      </RSlider.Track>
      <RSlider.Thumb className="block h-5 w-5 rounded-none border-2 border-clinical-border bg-clinical-accent shadow-sm cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-clinical-accent" />
    </RSlider.Root>
  );
}
