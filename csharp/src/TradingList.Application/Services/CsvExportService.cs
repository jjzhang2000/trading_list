using System.Globalization;
using System.IO;
using System.Text;
using CsvHelper;
using CsvHelper.Configuration;
using TradingList.Core.Models;

namespace TradingList.Application.Services;

/// <summary>
/// CSV 导出服务
/// </summary>
public class CsvExportService
{
    private readonly ILogger<CsvExportService> _logger;

    public CsvExportService(ILogger<CsvExportService> logger)
    {
        _logger = logger;
    }

    /// <summary>
    /// 导出筛选结果为 CSV
    /// </summary>
    public async Task<string> ExportToCsvAsync(
        IEnumerable<TrendScore> scores,
        DateTime date,
        string outputDirectory = null)
    {
        var directory = outputDirectory ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "TradingList", "logs");
        
        Directory.CreateDirectory(directory);
        
        var fileName = $"listing-{date:yyyy-MM-dd_HHmmss}.csv";
        var filePath = Path.Combine(directory, fileName);
        
        var records = scores.Select(s => new CsvRecord
        {
            Rank = s.Rank,
            StockCode = s.StockCode,
            StockName = s.IsPortfolioStock ? $"*{s.StockName}" : s.StockName,
            StrengthScore = s.StrengthScore,
            SuperTrendScore = s.SuperTrendScore,
            VegasScore = s.VegasScore,
            BollingerScore = s.BollingerScore,
            OccScore = s.OccScore,
            SlopeScore = s.SlopeScore,
            SuperTrendAbovePct = s.SuperTrendAbovePct,
            VegasAbovePct = s.VegasAbovePct,
            Bandwidth = s.Bandwidth,
            OccAbovePct = s.OccAbovePct,
            SlopeLong = s.SlopeLong,
            IsPortfolioStock = s.IsPortfolioStock
        });
        
        using var writer = new StreamWriter(filePath, false, Encoding.UTF8);
        using var csv = new CsvWriter(writer, new CsvConfiguration(CultureInfo.InvariantCulture)
        {
            HasHeaderRecord = true,
        });
        
        await csv.WriteRecordsAsync(records);
        
        _logger.LogInformation("CSV 已导出: {FilePath}", filePath);
        return filePath;
    }

    private class CsvRecord
    {
        public int Rank { get; set; }
        public string StockCode { get; set; } = string.Empty;
        public string StockName { get; set; } = string.Empty;
        public decimal StrengthScore { get; set; }
        public decimal SuperTrendScore { get; set; }
        public decimal VegasScore { get; set; }
        public decimal BollingerScore { get; set; }
        public decimal OccScore { get; set; }
        public decimal SlopeScore { get; set; }
        public decimal SuperTrendAbovePct { get; set; }
        public decimal VegasAbovePct { get; set; }
        public decimal Bandwidth { get; set; }
        public decimal OccAbovePct { get; set; }
        public decimal SlopeLong { get; set; }
        public bool IsPortfolioStock { get; set; }
    }
}
