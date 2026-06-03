//+------------------------------------------------------------------+
//|                                      ExportRatesForGannNN.mq5    |
//|               Export OHLCV data for train_gann_step_model.py     |
//+------------------------------------------------------------------+
#property copyright "Example project"
#property version   "1.00"
#property script_show_inputs
#property strict

input string          InpSymbol        = "XAUUSD";
input ENUM_TIMEFRAMES InpTimeframe     = PERIOD_M15;
input int             InpBarsToExport  = 50000;
input string          InpOutputFile    = "XAUUSD_M15.csv";

void OnStart()
{
   string symbol = InpSymbol;
   if(symbol == "")
      symbol = _Symbol;

   if(!SymbolSelect(symbol, true))
   {
      Print("Failed to select symbol: ", symbol, " error=", GetLastError());
      return;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(symbol, InpTimeframe, 0, InpBarsToExport, rates);
   if(copied <= 0)
   {
      Print("CopyRates failed. error=", GetLastError());
      return;
   }

   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   int file = FileOpen(InpOutputFile, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(file == INVALID_HANDLE)
   {
      Print("FileOpen failed. file=", InpOutputFile, " error=", GetLastError());
      return;
   }

   FileWrite(file, "date", "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");

   for(int i = 0; i < copied; i++)
   {
      FileWrite(
         file,
         TimeToString(rates[i].time, TIME_DATE),
         TimeToString(rates[i].time, TIME_MINUTES),
         DoubleToString(rates[i].open, digits),
         DoubleToString(rates[i].high, digits),
         DoubleToString(rates[i].low, digits),
         DoubleToString(rates[i].close, digits),
         (long)rates[i].tick_volume,
         rates[i].spread,
         (long)rates[i].real_volume
      );
   }

   FileClose(file);
   Print("Exported ", copied, " bars to MQL5/Files/", InpOutputFile);
}
