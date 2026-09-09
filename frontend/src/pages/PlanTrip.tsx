import { type ReactElement, cloneElement, isValidElement, useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { AddressInput } from '@/components/AddressInput';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';

import { ApiError, type PlanRequest, api } from '@/lib/api';

const HEADER_FIELDS: { name: keyof PlanRequest; label: string }[] = [
  { name: 'driver_name', label: 'Driver name' },
  { name: 'co_driver_name', label: 'Co-driver name' },
  { name: 'carrier_name', label: 'Carrier name' },
  { name: 'main_office_address', label: 'Main office address' },
  { name: 'home_terminal_address', label: 'Home terminal address' },
  { name: 'tractor_number', label: 'Tractor number' },
  { name: 'trailer_number', label: 'Trailer number' },
  { name: 'shipper_name', label: 'Shipper name' },
  { name: 'commodity', label: 'Commodity' },
  { name: 'shipping_doc_number', label: 'Shipping doc / manifest no.' },
];

export function PlanTrip() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [showHeader, setShowHeader] = useState(false);
  const [form, setForm] = useState<PlanRequest>({
    current_location: '',
    pickup_location: '',
    dropoff_location: '',
    current_cycle_used_h: 0,
    departure_at: '',
    use_split_sleeper: false,
  });

  const set = <K extends keyof PlanRequest>(k: K, v: PlanRequest[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload: PlanRequest = {
        ...form,
        current_cycle_used_h: Number(form.current_cycle_used_h) || 0,
        departure_at: form.departure_at || null,
      };
      const plan = await api.planTrip(payload);
      toast.success('Trip planned', { description: `${plan.summary.total_days} log sheet(s) generated` });
      navigate(`/trips/${plan.id}`, { state: { plan } });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Something went wrong';
      toast.error('Could not plan trip', { description: msg });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Plan a trip</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter the route and current cycle. You get a map with stops and a filled FMCSA log sheet for each day.
        </p>
      </div>

      <form onSubmit={submit}>
        {/* overflow-visible so the address autocomplete panels aren't clipped */}
        <Card className="overflow-visible">
          <CardHeader>
            <CardTitle className="text-base">Route &amp; cycle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Current location" required>
              <AddressInput
                required
                placeholder="Joplin, MO"
                value={form.current_location}
                onValueChange={(v) => set('current_location', v)}
              />
            </Field>
            <Field label="Pickup location" required>
              <AddressInput
                required
                placeholder="Council Bluffs, IA"
                value={form.pickup_location}
                onValueChange={(v) => set('pickup_location', v)}
              />
            </Field>
            <Field label="Dropoff location" required>
              <AddressInput
                required
                placeholder="Saint Louis, MO"
                value={form.dropoff_location}
                onValueChange={(v) => set('dropoff_location', v)}
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Current cycle used (hrs)" required hint="On-duty hours already used against the 70 hr / 8 day limit">
                <Input
                  required
                  type="number"
                  min={0}
                  max={70}
                  step={0.25}
                  value={form.current_cycle_used_h}
                  onChange={(e) => set('current_cycle_used_h', e.target.value as unknown as number)}
                />
              </Field>
              <Field label="Departure" hint="Defaults to now">
                <Input
                  type="datetime-local"
                  value={form.departure_at ?? ''}
                  onChange={(e) => set('departure_at', e.target.value)}
                />
              </Field>
            </div>

            <label className="flex items-start gap-2.5 rounded-md border border-border p-3">
              <Checkbox
                checked={form.use_split_sleeper}
                onCheckedChange={(v) => set('use_split_sleeper', Boolean(v))}
                className="mt-0.5"
              />
              <span className="text-sm">
                <span className="font-medium">Use split sleeper berth</span>
                <span className="block text-xs text-muted-foreground">
                  Plan 8/2 splits (§395.1(g)) instead of a straight 10-hour reset.
                </span>
              </span>
            </label>

            <Separator />

            <button
              type="button"
              onClick={() => setShowHeader((s) => !s)}
              aria-expanded={showHeader}
              className="-mx-1 rounded-sm px-1 text-sm font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {showHeader ? '− Hide' : '+ Add'} log header details (optional)
            </button>
            {showHeader && (
              <div className="grid grid-cols-2 gap-3">
                {HEADER_FIELDS.map((f) => (
                  <Field key={f.name} label={f.label}>
                    <Input value={(form[f.name] as string) ?? ''} onChange={(e) => set(f.name, e.target.value as never)} />
                  </Field>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Button type="submit" className="mt-4 w-full" disabled={busy}>
          {busy ? 'Planning route…' : 'Plan trip'}
        </Button>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Routing via OSRM · geocoding via Nominatim · address hints via Photon
        </p>
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  // Wire the visible label and helper text to the control for screen readers.
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, { id, 'aria-describedby': hintId })
    : children;

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs">
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {control}
      {hint && (
        <p id={hintId} className="text-xs leading-tight text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}
