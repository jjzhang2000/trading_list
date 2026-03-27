using Skender.Stock.Indicators;
using TradingList.Core.Enums;
using TradingList.Core.Interfaces;
using TradingList.Core.Models;

namespace TradingList.Infrastructure.Services;

/// <summary>
/// 技术指标服务实现
/// </summary>
public class TechnicalIndicatorService : ITechnicalIndicatorService
{
    private readonly IStockDataRepository _repository;
    private readonly ILogger<TechnicalIndicatorService> _logger;

    public TechnicalIndicatorService(
        IStockDataRepository repository,
        ILogger<TechnicalIndicatorService> logger)
    {
        _repository = repository;
        _logger = logger;
    }

    public async Task<SuperTrendResult?> CalculateSuperTrendAsync(
        string stockCode,
        DateTime date,
        int period = 10,
        decimal multiplier = 3.0m)
    {
        try
        {
            var minRequired = period + 50;
            var prices = await _repository.GetStockPriceBeforeDateAsync(stockCode, date, minRequired);
            
            if (prices.Count() < period + 10)
            {
                _logger.LogWarning("SuperTrend: 股票 {StockCode} 数据不足", stockCode);
                return null;
            }

            var quotes = prices.Select(p => new Quote
            {
                Date = p.Date,
                Open = (double)p.Open,
                High = (double)p.High,
                Low = (double)p.Low,
                Close = (double)p.Close,
                Volume = (double)p.Volume
            }).ToList();

            var superTrend = quotes.GetSuperTrend(period, (double)multiplier).LastOrDefault();
            
            if (superTrend == null)
                return null;

            var lastPrice = prices.Last();
            var trendDirection = superTrend.SuperTrend > superTrend.Close 
                ? TrendDirection.Bearish 
                : TrendDirection.Bullish;

            return new SuperTrendResult
            {
                StockCode = stockCode,
                Date = lastPrice.Date,
                Close = lastPrice.Close,
                SuperTrendValue = (decimal)superTrend.SuperTrend,
                TrendDirection = trendDirection
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "计算 SuperTrend 失败: {StockCode}", stockCode);
            return null;
        }
    }

    public async Task<VegasChannelResult?> CalculateVegasChannelAsync(
        string stockCode,
        DateTime date)
    {
        try
        {
            const int minRequired = 1000;
            var prices = await _repository.GetStockPriceBeforeDateAsync(stockCode, date, minRequired);
            
            if (prices.Count() < 676)
            {
                _logger.LogWarning("Vegas: 股票 {StockCode} 数据不足", stockCode);
                return null;
            }

            var quotes = prices.Select(p => new Quote
            {
                Date = p.Date,
                Close = (double)p.Close
            }).ToList();

            // 计算 6 条 EMA
            var ema12 = quotes.GetEma(12).Last();
            var ema26 = quotes.GetEma(26).Last();
            var ema144 = quotes.GetEma(144).Last();
            var ema169 = quotes.GetEma(169).Last();
            var ema576 = quotes.GetEma(576).Last();
            var ema676 = quotes.GetEma(676).Last();

            var lastPrice = prices.Last();
            var close = (double)lastPrice.Close;

            // 判断趋势方向
            var trendDirection = TrendDirection.Neutral;
            if (ema12.Ema > ema26.Ema && ema26.Ema > ema144.Ema && 
                ema144.Ema > ema169.Ema && ema169.Ema > ema576.Ema && 
                ema576.Ema > ema676.Ema)
            {
                trendDirection = TrendDirection.Bullish;
            }
            else if (ema12.Ema < ema26.Ema && ema26.Ema < ema144.Ema && 
                     ema144.Ema < ema169.Ema && ema169.Ema < ema576.Ema && 
                     ema576.Ema < ema676.Ema)
            {
                trendDirection = TrendDirection.Bearish;
            }

            return new VegasChannelResult
            {
                StockCode = stockCode,
                Date = lastPrice.Date,
                Close = lastPrice.Close,
                Ema12 = (decimal)ema12.Ema,
                Ema26 = (decimal)ema26.Ema,
                Ema144 = (decimal)ema144.Ema,
                Ema169 = (decimal)ema169.Ema,
                Ema576 = (decimal)ema576.Ema,
                Ema676 = (decimal)ema676.Ema,
                TrendDirection = trendDirection
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "计算 Vegas 通道失败: {StockCode}", stockCode);
            return null;
        }
    }

    public async Task<BollingerBandResult?> CalculateBollingerBandAsync(
        string stockCode,
        DateTime date,
        int period = 21,
        decimal stdDev = 2.0m)
    {
        try
        {
            var minRequired = period + 50;
            var prices = await _repository.GetStockPriceBeforeDateAsync(stockCode, date, minRequired);
            
            if (prices.Count() < period + 10)
            {
                _logger.LogWarning("布林带: 股票 {StockCode} 数据不足", stockCode);
                return null;
            }

            var quotes = prices.Select(p => new Quote
            {
                Date = p.Date,
                Close = (double)p.Close
            }).ToList();

            var bb = quotes.GetBollingerBands(period, (double)stdDev).LastOrDefault();
            
            if (bb == null)
                return null;

            var lastPrice = prices.Last();

            return new BollingerBandResult
            {
                StockCode = stockCode,
                Date = lastPrice.Date,
                Close = lastPrice.Close,
                MiddleBand = (decimal)bb.Sma,
                UpperBand = (decimal)bb.UpperBand,
                LowerBand = (decimal)bb.LowerBand
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "计算布林带失败: {StockCode}", stockCode);
            return null;
        }
    }

    public async Task<OccResult?> CalculateOccAsync(
        string stockCode,
        DateTime date,
        int period = 8,
        MaType maType = MaType.TMA)
    {
        try
        {
            var minRequired = period + 50;
            var prices = await _repository.GetStockPriceBeforeDateAsync(stockCode, date, minRequired);
            
            if (prices.Count() < period + 10)
            {
                _logger.LogWarning("OCC: 股票 {StockCode} 数据不足", stockCode);
                return null;
            }

            var quotes = prices.Select(p => new Quote
            {
                Date = p.Date,
                Open = (double)p.Open,
                Close = (double)p.Close
            }).ToList();

            // 计算开盘价的 MA
            var openMa = CalculateMA(quotes, q => q.Open, period, maType).Last();
            // 计算收盘价的 MA
            var closeMa = CalculateMA(quotes, q => q.Close, period, maType).Last();

            var lastPrice = prices.Last();
            var trendDirection = closeMa > openMa ? TrendDirection.Bullish : TrendDirection.Bearish;

            return new OccResult
            {
                StockCode = stockCode,
                Date = lastPrice.Date,
                Close = lastPrice.Close,
                OccOpen = (decimal)openMa,
                OccClose = (decimal)closeMa,
                TrendDirection = trendDirection
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "计算 OCC 失败: {StockCode}", stockCode);
            return null;
        }
    }

    public async Task<VpSlopeResult?> CalculateVpSlopeAsync(
        string stockCode,
        DateTime date,
        int periodLong = 100,
        int periodShort = 10)
    {
        try
        {
            var minRequired = periodLong + 50;
            var prices = await _repository.GetStockPriceBeforeDateAsync(stockCode, date, minRequired);
            
            if (prices.Count() < periodLong + 10)
            {
                _logger.LogWarning("VP Slope: 股票 {StockCode} 数据不足", stockCode);
                return null;
            }

            var quotes = prices.Select(p => new Quote
            {
                Date = p.Date,
                Close = (double)p.Close
            }).ToList();

            // 线性回归计算斜率
            var slopeLong = quotes.GetLinearRegression(periodLong).Last();
            var slopeShort = quotes.GetLinearRegression(periodShort).Last();

            var lastPrice = prices.Last();
            var trendDirection = slopeLong.Slope > 0 ? TrendDirection.Bullish : TrendDirection.Bearish;

            return new VpSlopeResult
            {
                StockCode = stockCode,
                Date = lastPrice.Date,
                Close = lastPrice.Close,
                SlopeLong = (decimal)slopeLong.Slope,
                SlopeShort = (decimal)slopeShort.Slope,
                TrendDirection = trendDirection
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "计算 VP Slope 失败: {StockCode}", stockCode);
            return null;
        }
    }

    private static IEnumerable<double> CalculateMA(
        List<Quote> quotes,
        Func<Quote, double> selector,
        int period,
        MaType maType)
    {
        var values = quotes.Select(selector).ToList();
        
        switch (maType)
        {
            case MaType.TMA:
                // 三角移动平均 = SMA(SMA(values))
                var sma1 = values.GetSma(period).Select(s => s.Sma ?? 0).ToList();
                return sma1.GetSma(period).Select(s => s.Sma ?? 0);
            
            case MaType.EMA:
                return values.GetEma(period).Select(s => s.Ema ?? 0);
            
            case MaType.SMA:
                return values.GetSma(period).Select(s => s.Sma ?? 0);
            
            case MaType.WMA:
                return values.GetWma(period).Select(s => s.Wma ?? 0);
            
            default:
                return values.GetEma(period).Select(s => s.Ema ?? 0);
        }
    }
}
