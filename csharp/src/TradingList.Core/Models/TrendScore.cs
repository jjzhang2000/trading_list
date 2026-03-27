namespace TradingList.Core.Models;

/// <summary>
/// 趋势评分结果
/// </summary>
public class TrendScore
{
    public string StockCode { get; set; } = string.Empty;
    public string StockName { get; set; } = string.Empty;
    
    /// <summary>
    /// 综合强度评分（加权平均）
    /// </summary>
    public decimal StrengthScore { get; set; }
    
    /// <summary>
    /// 各指标评分
    /// </summary>
    public decimal SuperTrendScore { get; set; }
    public decimal VegasScore { get; set; }
    public decimal BollingerScore { get; set; }
    public decimal OccScore { get; set; }
    public decimal SlopeScore { get; set; }
    
    /// <summary>
    /// 各指标原始值
    /// </summary>
    public decimal SuperTrendAbovePct { get; set; }
    public decimal VegasAbovePct { get; set; }
    public decimal Bandwidth { get; set; }
    public decimal OccAbovePct { get; set; }
    public decimal SlopeLong { get; set; }
    
    /// <summary>
    /// 是否为持仓股票
    /// </summary>
    public bool IsPortfolioStock { get; set; }
    
    /// <summary>
    /// 排名
    /// </summary>
    public int Rank { get; set; }
    
    /// <summary>
    /// 强度标签
    /// </summary>
    public string StrengthLabel => GetStrengthLabel(StrengthScore);
    
    private static string GetStrengthLabel(decimal score) => score switch
    {
        >= 8 => "极强",
        >= 6 => "很强",
        >= 4 => "较强",
        >= 2 => "一般",
        _ => "较弱"
    };
}
