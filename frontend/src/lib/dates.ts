/** Business dates follow the farm's timezone, regardless of device location. */
export function farmDate(value = new Date()): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone: 'America/Managua', year: 'numeric', month: '2-digit', day: '2-digit'
	}).format(value);
}

export function addDateDays(date: string, days: number): string {
	const value = new Date(`${date}T12:00:00Z`);
	value.setUTCDate(value.getUTCDate() + days);
	return value.toISOString().slice(0, 10);
}
