import { currentLocale } from './i18n';

// Reuse Steam's locale detection while keeping the update notice self-contained.
const notices: Record<string, [string, string]> = {
  en: ['Updated automatically to {version}.', 'Update {version} failed. Retry from the game’s SkullKey page.'],
  fr: ['Mis à jour automatiquement vers {version}.', 'Échec de la mise à jour {version}. Réessayez depuis la fiche SkullKey du jeu.'],
  de: ['Automatisch auf {version} aktualisiert.', 'Update {version} fehlgeschlagen. Erneut über die SkullKey-Spielseite versuchen.'],
  es: ['Actualizado automáticamente a {version}.', 'Falló la actualización {version}. Reinténtala desde la ficha del juego en SkullKey.'],
  it: ['Aggiornato automaticamente a {version}.', 'Aggiornamento {version} non riuscito. Riprova dalla pagina del gioco in SkullKey.'],
  pt: ['Atualizado automaticamente para {version}.', 'Falha na atualização {version}. Tente novamente na página do jogo no SkullKey.'],
  nl: ['Automatisch bijgewerkt naar {version}.', 'Update {version} mislukt. Probeer opnieuw via de spelpagina in SkullKey.'],
  pl: ['Automatycznie zaktualizowano do {version}.', 'Aktualizacja {version} nie powiodła się. Spróbuj ponownie na stronie gry w SkullKey.'],
  ru: ['Автоматически обновлено до {version}.', 'Не удалось обновить до {version}. Повторите попытку на странице игры в SkullKey.'],
};

export function portUpdateNotice(success: boolean, version: string): string {
  return (notices[currentLocale()] || notices.en)[success ? 0 : 1].replace('{version}', version);
}
