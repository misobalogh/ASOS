# Demo: price scout (Bazos + Alza MCP)

Spusti `claude` v tomto priecinku. `CLAUDE.md` ho nastavi ako cenoveho prieskumnika a `.claude/settings.json` povoli oba MCP
servery, takze na javke nevyskakuju potvrdzovacie okna.

## Pred prednaskou (10 minut vopred)

1. Tailscale bezi na tomto stroji (servery su na Chronose, `<chronos-ip>`).
2. `python3 preflight.py` musi vypisat 3x `OK` (Bazos, Alza, ISIC session). Zaroven zahreje Alza server (prve hladanie po
   restarte byva prazdne).
3. `claude mcp list` ukaze `bazos-chronos` a `alza` ako connected. Ak ma Alza "session expired", spusti `/mcp` a reconnect.
4. Ak `preflight.py` hlasi, ze ISIC chyba: `~/code/chronos-mcp/scripts/refresh-alza-session.sh`.
5. Terminal: zvacsi pismo, vypni notifikacie, svetle/tmave tema podla projektora.

## Dotaz na demo

Rozpocet na slajdoch je 600 EUR (v cene z 10. 10. 2026 mala pouzita RTX 4070 na Bazosi 550-600 EUR, do 450 EUR nebolo skoro nic).

> Chcem RTX 4070 alebo podobny vykon do 600 EUR, novu alebo z bazaru.

Ocakavanie: Bazos vrati niekolko pouzitych kariet (Palit Dual 550, NVIDIA RTX 4070 600, MSI 4070 SUPER 580), Alza dnes ma s RTX 4070
len notebooky a PC od 1 019 EUR, takze agent by mal povedat, ze nova RTX 4070 v rozpocte nie je, a hladat podobny vykon (napr. RTX 5060 Ti / 5070, RX 9070) na Alze aj na Bazosi.
Na Alze je dnes RTX 5060 Ti od 516 EUR (Palit, Gainward; len 8 GB oproti 12 GB u RTX 4070, dobry bod na diskusiu). Pozor: hladanie "grafická karta RTX 5070" vrati nic, funguje "GeForce RTX 5060 Ti"; agent si moze pomoct nastrojom `autocomplete`. Ceny sa menia, pred
prednaskou dotaz vyskusaj. Ak chces ukazat aj nove s ISIC zlavou, vhodny zaloznik je `MacBook Air do 1000 EUR`
(Alza nove M5 okolo 1 339 EUR, ISIC -7 %; Bazos pouzite M1/M2).

Dalsie dotazy na ukazku:
- `Najdi na Alze notebooky so zlavou aspon 30 %.` (get_deals)
- `Aka je bezna cena pouziteho MacBooku Air M2 na Bazosi?` (price_stats)
- `Porovnaj dva najlacnejsie nove MacBooky Air.` (compare_products)

## Multiagentove demo (LangGraph a CrewAI)

Tok zo slajdu `router -> bazos_scout || alza_scout -> analytik -> reporter` bezi v `agents/`. Obe verzie pouzivaju tie iste MCP servery (URL a tokeny cita z `~/.claude.json`) a Gemini
z `../.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`; `.env` je v `.gitignore`). Prompty vsetkych agentov su v `agents/prompts.py`
v poradi toku, obe verzie pouzivaju rovnake.

```
cd agents
uv sync
uv run python langgraph_demo.py     # asks "Question>" in a loop: type your own, Enter = example, q = quit
uv run python crewai_demo.py        # same, built as CrewAI Flow
uv run python langgraph_demo.py "iPhone 13 do 300 EUR"   # one question without the prompt
```

- Kazdy beh trva okolo minuty. Free tier Gemini ma limit 15 poziadaviek za minutu, takze dva behy hned po sebe mozu
  skoncit chybou 429: po jednom behu pockaj minutu, alebo pouzi plateny kluc.
- Scout dostane len nastroje svojho servera (least privilege), oba servery su len na citanie.
- Odkaz pri novom produkte si LLM obcas domysli (napr. len `alza.sk`); pred projektorom porovnaj s vystupom nastroja.

## Zaloha, ak nieco zlyha

- Server nereaguje: `ssh <user>@<chronos-ip> 'cd ~/code/chronos-mcp && docker compose ps'`, potom
  `docker compose restart alza`.
- Siet na mieste nefunguje: nahraj si pred prednaskou obrazovku/video z uspesneho behu a pusti ho.
- Ak sa vysledky lisia od slajdov, je to v poriadku: data su zive.

## Na co si dat pozor

- ISIC cena je viazana na tvoj ucet, na projektore ju vidno (cena, nie osobne udaje).
- Tokeny v `~/.claude.json` nezobrazuj (necat `claude mcp get` na projektore).
- Demo je len na citanie: nic sa nekupuje ani neodosiela.
