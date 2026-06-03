//+------------------------------------------------------------------+
//|                                             GannNeuralStepEA.mq5 |
//|                     Example EA: Gann step optimized by ONNX GRU  |
//+------------------------------------------------------------------+
#property copyright "Example project"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

#define FEATURE_COUNT 8

input group "Model"
input bool   InpUseOnnxModel          = true;
input string InpModelFile             = "gann_step_gru.onnx";
input int    InpSequenceLength        = 50;
input string InpCandidateMultipliers  = "0.50,0.75,1.00,1.25,1.50,2.00,2.50,3.00";
input double InpFallbackMultiplier    = 1.25;

input group "Indicators"
input int    InpAtrPeriod             = 14;
input int    InpRsiPeriod             = 14;
input int    InpFastEmaPeriod         = 21;
input int    InpSlowEmaPeriod         = 55;
input int    InpGannLookback          = 96;
input int    InpVolumeLookback        = 50;

input group "Trading"
input bool   InpAllowTrading          = false;
input double InpFixedLots             = 0.10;
input double InpStopAtrMultiplier     = 1.50;
input double InpRiskReward            = 2.00;
input int    InpMaxSpreadPoints       = 350;
input ulong  InpMagic                 = 260603;
input int    InpDeviationPoints       = 30;

struct GannLevels
{
   double support;
   double resistance;
   bool   trendUp;
};

CTrade trade;

int    g_atrHandle      = INVALID_HANDLE;
int    g_rsiHandle      = INVALID_HANDLE;
int    g_fastEmaHandle  = INVALID_HANDLE;
int    g_slowEmaHandle  = INVALID_HANDLE;
long   g_onnxHandle     = INVALID_HANDLE;
double g_candidates[];
datetime g_lastBarTime  = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpSequenceLength < 10)
   {
      Print("InpSequenceLength must be at least 10.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(!ParseCandidateMultipliers())
      return INIT_PARAMETERS_INCORRECT;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);

   g_atrHandle = iATR(_Symbol, _Period, InpAtrPeriod);
   g_rsiHandle = iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE);
   g_fastEmaHandle = iMA(_Symbol, _Period, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_slowEmaHandle = iMA(_Symbol, _Period, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(g_atrHandle == INVALID_HANDLE || g_rsiHandle == INVALID_HANDLE ||
      g_fastEmaHandle == INVALID_HANDLE || g_slowEmaHandle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. Error: ", GetLastError());
      return INIT_FAILED;
   }

   if(InpUseOnnxModel)
      LoadOnnxModel();

   Print("GannNeuralStepEA initialized on ", _Symbol, " ", EnumToString(_Period));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_onnxHandle != INVALID_HANDLE)
      OnnxRelease(g_onnxHandle);

   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
   if(g_rsiHandle != INVALID_HANDLE)
      IndicatorRelease(g_rsiHandle);
   if(g_fastEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_fastEmaHandle);
   if(g_slowEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_slowEmaHandle);
}

//+------------------------------------------------------------------+
//| Expert tick                                                       |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewClosedBar())
      return;

   if(!SymbolLooksLikeGold())
      Print("Warning: this EA is designed for XAUUSD/gold symbols. Current symbol: ", _Symbol);

   int spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
   {
      Print("Spread filter blocked trading. Spread points: ", spread);
      return;
   }

   int barsNeeded = InpSequenceLength + InpGannLookback + InpVolumeLookback + 5;
   MqlRates rates[];
   double atr[], rsi[], fastEma[], slowEma[];

   if(!LoadSeries(barsNeeded, rates, atr, rsi, fastEma, slowEma))
      return;

   float inputTensor[];
   if(!BuildFeatureTensor(rates, atr, rsi, fastEma, slowEma, inputTensor))
      return;

   double atrValue = atr[0];
   double closeValue = rates[0].close;
   double multiplier = PredictMultiplier(inputTensor, atrValue, closeValue);
   double gannStep = NormalizePrice(MathMax(atrValue * multiplier, _Point));

   GannLevels levels;
   if(!CalculateCurrentGannLevels(rates, atr, fastEma, slowEma, gannStep, levels))
      return;

   string directionText = levels.trendUp ? "BUY bias" : "SELL bias";
   PrintFormat("NN multiplier=%.2f ATR=%.2f GannStep=%.2f %s support=%.2f resistance=%.2f",
               multiplier, atrValue, gannStep, directionText, levels.support, levels.resistance);

   if(!InpAllowTrading || HasOpenPosition())
      return;

   TryOpenPosition(levels, atrValue);
}

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+
bool ParseCandidateMultipliers()
{
   string parts[];
   int count = StringSplit(InpCandidateMultipliers, ',', parts);
   if(count <= 0)
   {
      Print("No candidate multipliers configured.");
      return false;
   }

   ArrayResize(g_candidates, count);
   for(int i = 0; i < count; i++)
   {
      StringTrimLeft(parts[i]);
      StringTrimRight(parts[i]);
      double value = StringToDouble(parts[i]);
      if(value <= 0.0)
      {
         Print("Invalid multiplier: ", parts[i]);
         return false;
      }
      g_candidates[i] = value;
   }
   return true;
}

void LoadOnnxModel()
{
   ResetLastError();
   g_onnxHandle = OnnxCreate(InpModelFile, ONNX_DEFAULT);
   if(g_onnxHandle == INVALID_HANDLE)
   {
      Print("ONNX model was not loaded. Falling back to ATR rule. File: ",
            InpModelFile, " Error: ", GetLastError());
      return;
   }

   long inputShape[3];
   inputShape[0] = 1;
   inputShape[1] = InpSequenceLength;
   inputShape[2] = FEATURE_COUNT;

   long outputShape[2];
   outputShape[0] = 1;
   outputShape[1] = ArraySize(g_candidates);

   if(!OnnxSetInputShape(g_onnxHandle, 0, inputShape))
   {
      Print("Failed to set ONNX input shape. Error: ", GetLastError());
      OnnxRelease(g_onnxHandle);
      g_onnxHandle = INVALID_HANDLE;
      return;
   }

   if(!OnnxSetOutputShape(g_onnxHandle, 0, outputShape))
   {
      Print("Failed to set ONNX output shape. Error: ", GetLastError());
      OnnxRelease(g_onnxHandle);
      g_onnxHandle = INVALID_HANDLE;
      return;
   }

   Print("ONNX model loaded: ", InpModelFile);
}

bool IsNewClosedBar()
{
   datetime barTime = iTime(_Symbol, _Period, 1);
   if(barTime == 0 || barTime == g_lastBarTime)
      return false;

   g_lastBarTime = barTime;
   return true;
}

bool SymbolLooksLikeGold()
{
   string symbol = _Symbol;
   StringToUpper(symbol);
   return (StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "GOLD") >= 0);
}

bool LoadSeries(const int barsNeeded,
                MqlRates &rates[],
                double &atr[],
                double &rsi[],
                double &fastEma[],
                double &slowEma[])
{
   ArraySetAsSeries(rates, true);
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(rsi, true);
   ArraySetAsSeries(fastEma, true);
   ArraySetAsSeries(slowEma, true);

   int copiedRates = CopyRates(_Symbol, _Period, 1, barsNeeded, rates);
   if(copiedRates < barsNeeded)
   {
      Print("Not enough rates. Need ", barsNeeded, ", got ", copiedRates);
      return false;
   }

   if(CopyBuffer(g_atrHandle, 0, 1, barsNeeded, atr) < barsNeeded ||
      CopyBuffer(g_rsiHandle, 0, 1, barsNeeded, rsi) < barsNeeded ||
      CopyBuffer(g_fastEmaHandle, 0, 1, barsNeeded, fastEma) < barsNeeded ||
      CopyBuffer(g_slowEmaHandle, 0, 1, barsNeeded, slowEma) < barsNeeded)
   {
      Print("Failed to copy indicator buffers. Error: ", GetLastError());
      return false;
   }

   return true;
}

bool BuildFeatureTensor(MqlRates &rates[],
                        double &atr[],
                        double &rsi[],
                        double &fastEma[],
                        double &slowEma[],
                        float &inputTensor[])
{
   ArrayResize(inputTensor, InpSequenceLength * FEATURE_COUNT);

   for(int row = 0; row < InpSequenceLength; row++)
   {
      int shift = InpSequenceLength - 1 - row;
      if(atr[shift] <= 0.0 || rates[shift].close <= 0.0)
         return false;

      double closeOpenAtr = (rates[shift].close - rates[shift].open) / atr[shift];
      double rangeAtr = (rates[shift].high - rates[shift].low) / atr[shift];
      double returnAtr = (rates[shift].close - rates[shift + 1].close) / atr[shift];
      double rsiScaled = (rsi[shift] - 50.0) / 50.0;
      double emaGapAtr = (fastEma[shift] - slowEma[shift]) / atr[shift];
      double gannDistanceAtr = GannDistanceAtr(rates, atr, fastEma, slowEma, shift);
      double volumeZ = VolumeZScore(rates, shift, InpVolumeLookback);
      double atrPct = atr[shift] / rates[shift].close;

      int base = row * FEATURE_COUNT;
      inputTensor[base + 0] = (float)closeOpenAtr;
      inputTensor[base + 1] = (float)rangeAtr;
      inputTensor[base + 2] = (float)returnAtr;
      inputTensor[base + 3] = (float)rsiScaled;
      inputTensor[base + 4] = (float)emaGapAtr;
      inputTensor[base + 5] = (float)gannDistanceAtr;
      inputTensor[base + 6] = (float)volumeZ;
      inputTensor[base + 7] = (float)atrPct;
   }

   return true;
}

double GannDistanceAtr(MqlRates &rates[],
                       double &atr[],
                       double &fastEma[],
                       double &slowEma[],
                       const int shift)
{
   double swingLow = DBL_MAX;
   double swingHigh = -DBL_MAX;
   int maxIndex = MathMin(ArraySize(rates) - 1, shift + InpGannLookback - 1);

   for(int i = shift; i <= maxIndex; i++)
   {
      swingLow = MathMin(swingLow, rates[i].low);
      swingHigh = MathMax(swingHigh, rates[i].high);
   }

   bool trendUp = fastEma[shift] >= slowEma[shift];
   double basePrice = trendUp ? swingLow : swingHigh;
   double roughStep = MathMax(atr[shift] * InpFallbackMultiplier, _Point);
   double nearestLevel = basePrice + MathRound((rates[shift].close - basePrice) / roughStep) * roughStep;

   return (rates[shift].close - nearestLevel) / atr[shift];
}

double VolumeZScore(MqlRates &rates[], const int shift, const int lookback)
{
   int maxIndex = MathMin(ArraySize(rates) - 1, shift + lookback - 1);
   int count = maxIndex - shift + 1;
   if(count <= 1)
      return 0.0;

   double sum = 0.0;
   for(int i = shift; i <= maxIndex; i++)
      sum += (double)rates[i].tick_volume;

   double mean = sum / count;
   double variance = 0.0;
   for(int i = shift; i <= maxIndex; i++)
   {
      double diff = (double)rates[i].tick_volume - mean;
      variance += diff * diff;
   }

   double stdev = MathSqrt(variance / MathMax(count - 1, 1));
   if(stdev <= 0.0)
      return 0.0;

   return ((double)rates[shift].tick_volume - mean) / stdev;
}

double PredictMultiplier(float &inputTensor[], const double atrValue, const double closeValue)
{
   if(g_onnxHandle == INVALID_HANDLE)
      return FallbackMultiplier(atrValue, closeValue);

   float output[];
   ArrayResize(output, ArraySize(g_candidates));
   ArrayInitialize(output, 0.0);

   ResetLastError();
   if(!OnnxRun(g_onnxHandle, ONNX_DEFAULT, inputTensor, output))
   {
      Print("ONNX inference failed. Falling back to ATR rule. Error: ", GetLastError());
      return FallbackMultiplier(atrValue, closeValue);
   }

   int bestIndex = 0;
   for(int i = 1; i < ArraySize(output); i++)
   {
      if(output[i] > output[bestIndex])
         bestIndex = i;
   }

   return g_candidates[bestIndex];
}

double FallbackMultiplier(const double atrValue, const double closeValue)
{
   double atrPct = atrValue / MathMax(closeValue, _Point);
   double target = InpFallbackMultiplier;

   if(atrPct > 0.0060)
      target = 2.00;
   else if(atrPct > 0.0035)
      target = 1.50;
   else if(atrPct < 0.0015)
      target = 0.75;

   int bestIndex = 0;
   double bestDistance = MathAbs(g_candidates[0] - target);
   for(int i = 1; i < ArraySize(g_candidates); i++)
   {
      double distance = MathAbs(g_candidates[i] - target);
      if(distance < bestDistance)
      {
         bestDistance = distance;
         bestIndex = i;
      }
   }

   return g_candidates[bestIndex];
}

bool CalculateCurrentGannLevels(MqlRates &rates[],
                                double &atr[],
                                double &fastEma[],
                                double &slowEma[],
                                const double gannStep,
                                GannLevels &levels)
{
   if(gannStep <= 0.0)
      return false;

   double swingLow = DBL_MAX;
   double swingHigh = -DBL_MAX;
   int maxIndex = MathMin(ArraySize(rates) - 1, InpGannLookback - 1);

   for(int i = 0; i <= maxIndex; i++)
   {
      swingLow = MathMin(swingLow, rates[i].low);
      swingHigh = MathMax(swingHigh, rates[i].high);
   }

   levels.trendUp = fastEma[0] >= slowEma[0];
   double basePrice = levels.trendUp ? swingLow : swingHigh;
   double gridIndex = MathFloor((rates[0].close - basePrice) / gannStep);
   levels.support = NormalizePrice(basePrice + gridIndex * gannStep);
   levels.resistance = NormalizePrice(levels.support + gannStep);

   if(levels.resistance < levels.support)
   {
      double tmp = levels.resistance;
      levels.resistance = levels.support;
      levels.support = tmp;
   }

   return atr[0] > 0.0;
}

void TryOpenPosition(const GannLevels &levels, const double atrValue)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
      return;

   double gridWidth = MathAbs(levels.resistance - levels.support);
   if(gridWidth <= _Point)
      return;

   if(levels.trendUp)
   {
      double trigger = levels.support + 0.25 * gridWidth;
      if(bid <= trigger)
         return;

      double sl = NormalizePrice(MathMin(levels.support, bid - atrValue * InpStopAtrMultiplier));
      double risk = ask - sl;
      if(risk <= _Point)
         return;

      double tp = NormalizePrice(ask + risk * InpRiskReward);
      if(!trade.Buy(InpFixedLots, _Symbol, ask, sl, tp, "Gann NN buy"))
         Print("Buy failed. Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
   else
   {
      double trigger = levels.resistance - 0.25 * gridWidth;
      if(ask >= trigger)
         return;

      double sl = NormalizePrice(MathMax(levels.resistance, ask + atrValue * InpStopAtrMultiplier));
      double risk = sl - bid;
      if(risk <= _Point)
         return;

      double tp = NormalizePrice(bid - risk * InpRiskReward);
      if(!trade.Sell(InpFixedLots, _Symbol, bid, sl, tp, "Gann NN sell"))
         Print("Sell failed. Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }

   return false;
}

double NormalizePrice(const double price)
{
   return NormalizeDouble(price, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
}
