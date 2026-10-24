# Asystent on-call

Agent diagnozujący celowo wstrzykiwane awarie w demo mikroserwisów opartym na RabbitMQ i OpenTelemetry.

## Jak działa

- **Dostęp tylko do odczytu:** trace'y, metryki, logi i API RabbitMQ.
- **Wynik:** hipoteza przyczyny awarii wraz z dowodami (ID trace'ów, linie logów) oraz propozycja naprawy.
- **Człowiek w pętli:** każda propozycja naprawy wymaga zatwierdzenia przez człowieka — agent niczego sam nie zmienia.

## Ewaluacja

Agent jest oceniany na katalogu 20–30 wstrzykniętych awarii pod kątem:

1. **Trafności** — czy poprawnie wskazał przyczynę źródłową.
2. **Ugruntowania w dowodach** — odsetek diagnoz opartych na prawdziwych dowodach (bez zmyślonych ID trace'ów czy linii logów).
3. **Kosztu i czasu** — koszt oraz czas trwania jednej diagnozy.
