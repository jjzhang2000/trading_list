using System.Collections.Concurrent;
using TradingList.Core.Enums;
using TradingList.Core.Interfaces;
using TradingList.Core.Models;

namespace TradingList.Application.Services;

/// <summary>
/// 股票筛选服务
/// </summary>
public class StockFilterService
{
    private readonly IStockDataRepository _repository;
    private readonly ITechnicalIndicatorService _indicatorService;
    private readonly IStockDataService _dataService;
    private readonly IPortfolioService _portfolioService;
    private readonly ILogger<StockFilterService> _logger;

    public StockFilterService(
        IStockDataRepository repository,
        ITechnicalIndicatorService indicatorService,
        IStockDataService dataService,
        IPortfolioService portfolioService,
        ILogger<StockFilterService> logger)
    {
        _repository = repository;
        _indicatorService = indicatorService;
        _dataService = dataService;
        _portfolioService = portfolioService;
        _logger = logger;
    }

    /// <summary>
    /// 执行股票筛选
    /// </summary>
    public async Task<IEnumerable<TrendScore>> FilterStocksAsync(
        FilterOptions options,
        IProgress<string> progress,
        CancellationToken cancellationToken = default)
    {
        var date = options.Date;
        progress.Report($"开始筛选，日期: {date:yyyy-MM-dd}");
        
        // 1. 获取所有股票代码
        var stockCodes = await _repository.GetAllStockCodesAsync();
        progress.Report($"数据库中共有 {stockCodes.Count()} 只股票");
        
        // 2. 过滤 ST 股票（名称中包含 ST）
        var validStocks = await FilterStStocksAsync(stockCodes);
        progress.Report($"过滤 ST 股票后剩余 {validStocks.Count()} 只");
        
        // 3. 顺序执行技术指标筛选
        var filteredStocks = validStocks.ToList();
        
        if (options.EnableSuperTrend)
        {
            filteredStocks = await FilterBySuperTrendAsync(filteredStocks, date, progress, cancellationToken);
        }
        
        if (options.EnableVegas)
        {
            filteredStocks = await FilterByVegasAsync(filteredStocks, date, progress, cancellationToken);
        }
        
        if (options.EnableBollingerBand)
        {
            filteredStocks = await FilterByBollingerBandAsync(
                filteredStocks, date, options.BollingerBandwidthThreshold, progress, cancellationToken);
        }
        
        if (options.EnableOcc)
        {
            filteredStocks = await FilterByOccAsync(
                filteredStocks, date, options.OccPeriod, options.OccMaType, progress, cancellationToken);
        }
        
        if (options.EnableVpSlope)
        {
            filteredStocks = await FilterByVpSlopeAsync(
                filteredStocks, date, options.VpSlopeLongPeriod, options.VpSlopeShortPeriod, progress, cancellationToken);
        }
        
        // 4. 获取持仓股票并加入筛选结果
        var portfolioStocks = await _portfolioService.GetPortfolioStocksAsync();
        progress.Report($"持仓股票: {portfolioStocks.Count()} 只");
        
        // 合并筛选结果和持仓股票
        var allStocks = filteredStocks.Union(portfolioStocks).Distinct().ToList();
        
        // 5. 计算趋势强度评分
        var scores = await CalculateTrendScoresAsync(
            allStocks, date, portfolioStocks, options, progress, cancellationToken);
        
        // 6. 排序
        var rankedScores = scores
            .OrderByDescending(s => s.StrengthScore)
            .Select((s, index) => { s.Rank = index + 1; return s; })
            .ToList();
        
        progress.Report($"筛选完成，共 {rankedScores.Count} 只股票");
        
        return rankedScores;
    }

    /// <summary>
    /// 过滤 ST 股票
    /// </summary>
    private async Task<IEnumerable<string>> FilterStStocksAsync(IEnumerable<string> stockCodes)
    {
        var result = new List<string>();
        
        foreach (var code in stockCodes)
        {
            var name = await _repository.GetStockNameAsync(code);
            if (!string.IsNullOrEmpty(name) && !name.Contains("ST"))
            {
                result.Add(code);
            }
        }
        
        return result;
    }

    /// <summary>
    /// SuperTrend 筛选
    /// </summary>
    private async Task<List<string>> FilterBySuperTrendAsync(
        List<string> stockCodes,
        DateTime date,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var results = new ConcurrentBag<string>();
        var count = 0;
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            var result = await _indicatorService.CalculateSuperTrendAsync(code, date);
            
            if (result?.TrendDirection == TrendDirection.Bullish)
            {
                results.Add(code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  SuperTrend 筛选: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"SuperTrend 筛选后剩余 {results.Count} 只");
        return results.ToList();
    }

    /// <summary>
    /// Vegas 通道筛选
    /// </summary>
    private async Task<List<string>> FilterByVegasAsync(
        List<string> stockCodes,
        DateTime date,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var results = new ConcurrentBag<string>();
        var count = 0;
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            var result = await _indicatorService.CalculateVegasChannelAsync(code, date);
            
            if (result?.TrendDirection == TrendDirection.Bullish)
            {
                results.Add(code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  Vegas 通道筛选: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"Vegas 通道筛选后剩余 {results.Count} 只");
        return results.ToList();
    }

    /// <summary>
    /// 布林带筛选
    /// </summary>
    private async Task<List<string>> FilterByBollingerBandAsync(
        List<string> stockCodes,
        DateTime date,
        decimal threshold,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var results = new ConcurrentBag<string>();
        var count = 0;
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            var result = await _indicatorService.CalculateBollingerBandAsync(code, date);
            
            if (result != null && 
                result.Bandwidth > threshold && 
                result.IsAboveMiddle)
            {
                results.Add(code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  布林带筛选: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"布林带筛选后剩余 {results.Count} 只");
        return results.ToList();
    }

    /// <summary>
    /// OCC 筛选
    /// </summary>
    private async Task<List<string>> FilterByOccAsync(
        List<string> stockCodes,
        DateTime date,
        int period,
        MaType maType,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var results = new ConcurrentBag<string>();
        var count = 0;
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            var result = await _indicatorService.CalculateOccAsync(code, date, period, maType);
            
            if (result?.TrendDirection == TrendDirection.Bullish)
            {
                results.Add(code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  OCC 筛选: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"OCC 筛选后剩余 {results.Count} 只");
        return results.ToList();
    }

    /// <summary>
    /// VP Slope 筛选
    /// </summary>
    private async Task<List<string>> FilterByVpSlopeAsync(
        List<string> stockCodes,
        DateTime date,
        int periodLong,
        int periodShort,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var results = new ConcurrentBag<string>();
        var count = 0;
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            var result = await _indicatorService.CalculateVpSlopeAsync(code, date, periodLong, periodShort);
            
            if (result?.SlopeLong > 0)
            {
                results.Add(code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  VP Slope 筛选: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"VP Slope 筛选后剩余 {results.Count} 只");
        return results.ToList();
    }

    /// <summary>
    /// 计算趋势强度评分
    /// </summary>
    private async Task<List<TrendScore>> CalculateTrendScoresAsync(
        List<string> stockCodes,
        DateTime date,
        IEnumerable<string> portfolioStocks,
        FilterOptions options,
        IProgress<string> progress,
        CancellationToken cancellationToken)
    {
        var scores = new ConcurrentBag<TrendScore>();
        var count = 0;
        var portfolioSet = portfolioStocks.ToHashSet();
        
        await Parallel.ForEachAsync(stockCodes, new ParallelOptions 
        { 
            MaxDegreeOfParallelism = 4,
            CancellationToken = cancellationToken 
        }, async (code, ct) =>
        {
            try
            {
                var score = new TrendScore
                {
                    StockCode = code,
                    StockName = await _repository.GetStockNameAsync(code) ?? "",
                    IsPortfolioStock = portfolioSet.Contains(code)
                };
                
                // 计算各指标评分
                if (options.EnableSuperTrend)
                {
                    var st = await _indicatorService.CalculateSuperTrendAsync(code, date);
                    if (st != null)
                    {
                        score.SuperTrendScore = st.Score;
                        score.SuperTrendAbovePct = st.AbovePercentage;
                    }
                }
                
                if (options.EnableVegas)
                {
                    var vegas = await _indicatorService.CalculateVegasChannelAsync(code, date);
                    if (vegas != null)
                    {
                        score.VegasScore = vegas.Score;
                        score.VegasAbovePct = vegas.AboveEma144Percentage;
                    }
                }
                
                if (options.EnableBollingerBand)
                {
                    var bb = await _indicatorService.CalculateBollingerBandAsync(code, date);
                    if (bb != null)
                    {
                        score.BollingerScore = bb.Score;
                        score.Bandwidth = bb.Bandwidth;
                    }
                }
                
                if (options.EnableOcc)
                {
                    var occ = await _indicatorService.CalculateOccAsync(code, date, options.OccPeriod, options.OccMaType);
                    if (occ != null)
                    {
                        score.OccScore = occ.Score;
                        score.OccAbovePct = occ.AbovePercentage;
                    }
                }
                
                if (options.EnableVpSlope)
                {
                    var slope = await _indicatorService.CalculateVpSlopeAsync(code, date, options.VpSlopeLongPeriod, options.VpSlopeShortPeriod);
                    if (slope != null)
                    {
                        score.SlopeScore = slope.Score;
                        score.SlopeLong = slope.SlopeLong;
                    }
                }
                
                // 计算综合评分（加权平均）
                // 权重：ST=1, Vegas=2, BB=1, OCC=1, Slope=1
                const decimal totalWeight = 6.0m;
                score.StrengthScore = (
                    score.SuperTrendScore * 1.0m +
                    score.VegasScore * 2.0m +
                    score.BollingerScore * 1.0m +
                    score.OccScore * 1.0m +
                    score.SlopeScore * 1.0m
                ) / totalWeight;
                
                scores.Add(score);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "计算股票 {StockCode} 评分失败", code);
            }
            
            var currentCount = Interlocked.Increment(ref count);
            if (currentCount % 100 == 0)
            {
                progress.Report($"  计算评分: {currentCount}/{stockCodes.Count}");
            }
        });
        
        progress.Report($"评分计算完成");
        return scores.ToList();
    }
}
