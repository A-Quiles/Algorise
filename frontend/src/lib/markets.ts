// Listas de mercado compartidas por la UI (Config y Backtesting).
// Se usan para los desplegables de moneda, así no hay que escribir el par a mano.

// Monedas de cotización (lo que tienes en cartera y la cotización de los pares).
export const QUOTE_CURRENCIES = ["USDT", "USDC", "EUR", "BUSD", "GBP", "TRY"];

// Criptos habituales; el par se forma como BASE/COTIZACIÓN (p.ej. BTC/USDT).
export const COMMON_COINS = [
  "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "MATIC",
  "LINK", "AVAX", "LTC", "TRX", "ATOM", "NEAR", "ARB", "OP", "INJ",
  "SUI", "APT", "FIL", "UNI", "AAVE", "ETC", "XLM", "ALGO",
];

// Construye el símbolo de par a partir de la cripto y la moneda de cotización.
export const makePair = (coin: string, quote: string): string => `${coin}/${quote}`;
