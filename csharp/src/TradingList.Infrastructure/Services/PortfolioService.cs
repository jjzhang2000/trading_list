using System.IO;
using TradingList.Core.Interfaces;

namespace TradingList.Infrastructure.Services;

/// <summary>
/// 持仓服务实现
/// </summary>
public class PortfolioService : IPortfolioService
{
    private readonly string _portfolioFilePath;
    private readonly ILogger<PortfolioService> _logger;

    public PortfolioService(ILogger<PortfolioService> logger)
    {
        _logger = logger;
        // 持仓文件放在应用根目录
        var appDir = AppDomain.CurrentDomain.BaseDirectory;
        _portfolioFilePath = Path.Combine(appDir, "..", "..", "..", "..", "..", "shareholding.txt");
        _portfolioFilePath = Path.GetFullPath(_portfolioFilePath);
    }

    public async Task<IEnumerable<string>> GetPortfolioStocksAsync()
    {
        try
        {
            if (!File.Exists(_portfolioFilePath))
            {
                return Enumerable.Empty<string>();
            }

            var lines = await File.ReadAllLinesAsync(_portfolioFilePath);
            return lines
                .Select(line => line.Trim())
                .Where(line => !string.IsNullOrEmpty(line) && line.All(char.IsDigit))
                .ToList();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "读取持仓文件失败: {FilePath}", _portfolioFilePath);
            return Enumerable.Empty<string>();
        }
    }

    public async Task AddPortfolioStockAsync(string stockCode)
    {
        try
        {
            var codes = (await GetPortfolioStocksAsync()).ToList();
            
            if (!codes.Contains(stockCode))
            {
                codes.Add(stockCode);
                await File.WriteAllLinesAsync(_portfolioFilePath, codes);
                _logger.LogInformation("添加持仓股票: {StockCode}", stockCode);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "添加持仓股票失败: {StockCode}", stockCode);
            throw;
        }
    }

    public async Task RemovePortfolioStockAsync(string stockCode)
    {
        try
        {
            var codes = (await GetPortfolioStocksAsync()).ToList();
            
            if (codes.Remove(stockCode))
            {
                await File.WriteAllLinesAsync(_portfolioFilePath, codes);
                _logger.LogInformation("移除持仓股票: {StockCode}", stockCode);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "移除持仓股票失败: {StockCode}", stockCode);
            throw;
        }
    }

    public async Task<bool> IsPortfolioStockAsync(string stockCode)
    {
        var codes = await GetPortfolioStocksAsync();
        return codes.Contains(stockCode);
    }
}
