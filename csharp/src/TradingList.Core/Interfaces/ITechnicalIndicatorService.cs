using TradingList.Core.Enums;
using TradingList.Core.Models;

namespace TradingList.Core.Interfaces;

/// <summary>
/// 技术指标服务接口
/// </summary>
public interface ITechnicalIndicatorService
{
    /// <summary>
    /// 计算 SuperTrend
    /// </summary>
    Task<SuperTrendResult?> CalculateSuperTrendAsync(
        string stockCode,
        DateTime date,
        int period = 10,
        decimal multiplier = 3.0m);
    
    /// <summary>
    /// 计算 Vegas 通道
    /// </summary>
    Task<VegasChannelResult?> CalculateVegasChannelAsync(
        string stockCode,
        DateTime date);
    
    /// <summary>
    /// 计算布林带
    /// </summary>
    Task<BollingerBandResult?> CalculateBollingerBandAsync(
        string stockCode,
        DateTime date,
        int period = 21,
        decimal stdDev = 2.0m);
    
    /// <summary>
    /// 计算 OCC
    /// </summary>
    Task<OccResult?> CalculateOccAsync(
        string stockCode,
        DateTime date,
        int period = 8,
        MaType maType = MaType.TMA);
    
    /// <summary>
    /// 计算 VP Slope
    /// </summary>
    Task<VpSlopeResult?> CalculateVpSlopeAsync(
        string stockCode,
        DateTime date,
        int periodLong = 100,
        int periodShort = 10);
}
