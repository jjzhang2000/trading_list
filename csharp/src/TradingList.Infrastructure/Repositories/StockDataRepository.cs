using Microsoft.EntityFrameworkCore;
using TradingList.Core.Interfaces;
using TradingList.Core.Models;
using TradingList.Infrastructure.Data;

namespace TradingList.Infrastructure.Repositories;

/// <summary>
/// 股票数据仓库实现
/// </summary>
public class StockDataRepository : IStockDataRepository
{
    private readonly TradingDbContext _context;

    public StockDataRepository(TradingDbContext context)
    {
        _context = context;
    }

    public async Task InitializeAsync()
    {
        await _context.Database.EnsureCreatedAsync();
    }

    public async Task<IEnumerable<string>> GetAllStockCodesAsync()
    {
        return await _context.StockPrices
            .Select(p => p.StockCode)
            .Distinct()
            .OrderBy(c => c)
            .ToListAsync();
    }

    public async Task<string?> GetStockNameAsync(string stockCode)
    {
        var info = await _context.StockInfos
            .FirstOrDefaultAsync(s => s.StockCode == stockCode);
        return info?.StockName;
    }

    public async Task<IEnumerable<StockPrice>> GetStockPriceBeforeDateAsync(
        string stockCode, 
        DateTime endDate, 
        int limit)
    {
        return await _context.StockPrices
            .Where(p => p.StockCode == stockCode && p.Date <= endDate)
            .OrderByDescending(p => p.Date)
            .Take(limit)
            .OrderBy(p => p.Date)
            .ToListAsync();
    }

    public async Task<IEnumerable<StockPrice>> GetStockPriceInRangeAsync(
        string stockCode,
        DateTime startDate,
        DateTime endDate)
    {
        return await _context.StockPrices
            .Where(p => p.StockCode == stockCode && p.Date >= startDate && p.Date <= endDate)
            .OrderBy(p => p.Date)
            .ToListAsync();
    }

    public async Task<IEnumerable<StockPrice>> GetAllStocksPriceOnDateAsync(DateTime date)
    {
        return await _context.StockPrices
            .Where(p => p.Date == date)
            .OrderBy(p => p.StockCode)
            .ToListAsync();
    }

    public async Task SaveStockPricesAsync(IEnumerable<StockPrice> prices)
    {
        foreach (var price in prices)
        {
            var existing = await _context.StockPrices
                .FirstOrDefaultAsync(p => p.StockCode == price.StockCode && p.Date == price.Date);
            
            if (existing != null)
            {
                // 更新现有记录
                _context.Entry(existing).CurrentValues.SetValues(price);
            }
            else
            {
                // 添加新记录
                await _context.StockPrices.AddAsync(price);
            }
        }
        
        await _context.SaveChangesAsync();
    }

    public async Task UpdateStockInfoAsync(StockInfo info)
    {
        var existing = await _context.StockInfos
            .FirstOrDefaultAsync(s => s.StockCode == info.StockCode);
        
        if (existing != null)
        {
            _context.Entry(existing).CurrentValues.SetValues(info);
        }
        else
        {
            await _context.StockInfos.AddAsync(info);
        }
        
        await _context.SaveChangesAsync();
    }

    public async Task<StockInfo?> GetStockInfoAsync(string stockCode)
    {
        return await _context.StockInfos
            .FirstOrDefaultAsync(s => s.StockCode == stockCode);
    }

    public async Task ClearDatabaseAsync()
    {
        await _context.StockPrices.ExecuteDeleteAsync();
        await _context.StockInfos.ExecuteDeleteAsync();
    }
}
