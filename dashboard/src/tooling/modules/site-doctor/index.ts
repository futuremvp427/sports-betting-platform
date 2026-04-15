export class SiteDoctor {
  runDiagnostics(): string[] {
    return ["API health check", "Odds provider status", "Database connectivity"];
  }
}
