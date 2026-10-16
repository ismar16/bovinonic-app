export const catalogConfig = {
	paddocks: { title: 'Potreros', singular: 'potrero', description: 'Lugares donde se ubican los animales de la finca.', field: 'name', max: 100 },
	owners: { title: 'Propietarios', singular: 'propietario', description: 'Titulares, identificación y datos de contacto.', field: 'name', max: 150 },
	brands: { title: 'Fierros', singular: 'fierro', description: 'Códigos de identificación y sus titulares.', field: 'code', max: 50 }
} as const;
export type CatalogKind = keyof typeof catalogConfig;
export function catalogKind(value?: string): CatalogKind | null {
	return value && Object.hasOwn(catalogConfig, value) ? value as CatalogKind : null;
}
export interface CatalogRecord { id: string; farm: string; name?: string; code?: string; id_number?: string; phone?: string; title_owner?: string | null; updated_at?: string; }
