export function errorMessage(error: unknown, fallback = 'No se pudo guardar. Tus datos siguen en el formulario.'): string {
	if (error instanceof Error && error.message && !error.message.startsWith('API ')) return error.message;
	if (error && typeof error === 'object' && 'body' in error) {
		const body = error.body as { detail?: string; errors?: Record<string, unknown> } | null;
		if (body?.errors && Object.keys(body.errors).length) {
			const names: Record<string, string> = { animals: 'Animales', lots: 'Lotes', agreements: 'Acuerdos', sales: 'Ventas', sale_payments: 'Cobros', sale_expenses: 'Gastos de venta', owners: 'Propietarios', paddocks: 'Potreros', brands: 'Fierros', milkings: 'Ordeños', daily_milk: 'Producción diaria', weighings: 'Pesajes', health_events: 'Sanidad', reproductive_events: 'Reproducción' };
			return Object.entries(body.errors).slice(0, 3).map(([collection, problems]) => {
				const rows = Array.isArray(problems) ? problems : [problems];
				const detail = rows.slice(0, 2).map((row) => row && typeof row === 'object' && 'error' in row ? JSON.stringify(row.error) : String(row)).join('; ');
				return `${names[collection] ?? collection}: ${detail}`;
			}).join(' · ');
		}
		if (body?.detail) return body.detail;
	}
	return fallback;
}

export function decimalValue(value: string, allowZero = false): number {
	const normalized = value.trim().replace(',', '.');
	if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error('Ingresá una cantidad válida con hasta dos decimales.');
	const number = Number(normalized);
	if (!Number.isFinite(number) || (allowZero ? number < 0 : number <= 0)) throw new Error('La cantidad debe ser mayor que cero.');
	return number;
}

export function validDate(value: string): boolean {
	return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T12:00:00Z`))
		&& new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
}
