using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradingList.Application.Services;
using TradingList.Core.Models;

namespace TradingList.WPF.ViewModels;

/// <summary>
/// 主窗口 ViewModel
/// </summary>
public partial class MainViewModel : ObservableObject
{
    private readonly StockFilterService _filterService;
    private readonly DataSyncService _dataSyncService;
    private readonly CsvExportService _csvExportService;
    private CancellationTokenSource _cancellationTokenSource;

    public MainViewModel(
        StockFilterService filterService,
        DataSyncService dataSyncService,
        CsvExportService csvExportService)
    {
        _filterService = filterService;
        _dataSyncService = dataSyncService;
        _csvExportService = csvExportService;
        
        FilterOptions = new FilterOptions();
        AllStocks = new ObservableCollection<StockViewModel>();
        FilteredStocks = new ObservableCollection<StockViewModel>();
        LogMessages = new ObservableCollection<string>();
    }

    #region Properties

    [ObservableProperty]
    private FilterOptions _filterOptions;

    [ObservableProperty]
    private ObservableCollection<StockViewModel> _allStocks;

    [ObservableProperty]
    private ObservableCollection<StockViewModel> _filteredStocks;

    [ObservableProperty]
    private ObservableCollection<string> _logMessages;

    [ObservableProperty]
    private bool _isBusy;

    [ObservableProperty]
    private double _progressValue;

    [ObservableProperty]
    private string _statusMessage = "就绪";

    [ObservableProperty]
    private int _totalStockCount;

    [ObservableProperty]
    private int _filteredStockCount;

    #endregion

    #region Commands

    [RelayCommand]
    private async Task InitializeDatabaseAsync()
    {
        try
        {
            IsBusy = true;
            StatusMessage = "正在初始化数据库...";
            
            var progress = new Progress<string>(msg =>
            {
                LogMessages.Add(msg);
                StatusMessage = msg;
            });
            
            await _dataSyncService.InitializeDatabaseAsync(progress);
            
            StatusMessage = "数据库初始化完成";
        }
        catch (Exception ex)
        {
            LogMessages.Add($"初始化数据库失败: {ex.Message}");
            StatusMessage = "初始化数据库失败";
        }
        finally
        {
            IsBusy = false;
        }
    }

    [RelayCommand]
    private async Task SyncDataAsync()
    {
        try
        {
            IsBusy = true;
            StatusMessage = "正在同步数据...";
            _cancellationTokenSource = new CancellationTokenSource();
            
            var progress = new Progress<string>(msg =>
            {
                LogMessages.Add($"[{DateTime.Now:HH:mm:ss}] {msg}");
                StatusMessage = msg;
            });
            
            await _dataSyncService.SyncAllStocksAsync(5, progress, _cancellationTokenSource.Token);
            
            StatusMessage = "数据同步完成";
        }
        catch (OperationCanceledException)
        {
            StatusMessage = "同步已取消";
        }
        catch (Exception ex)
        {
            LogMessages.Add($"同步数据失败: {ex.Message}");
            StatusMessage = "同步数据失败";
        }
        finally
        {
            IsBusy = false;
            _cancellationTokenSource?.Dispose();
            _cancellationTokenSource = null;
        }
    }

    [RelayCommand]
    private async Task RunFilterAsync()
    {
        try
        {
            IsBusy = true;
            StatusMessage = "正在筛选股票...";
            FilteredStocks.Clear();
            _cancellationTokenSource = new CancellationTokenSource();
            
            var progress = new Progress<string>(msg =>
            {
                LogMessages.Add($"[{DateTime.Now:HH:mm:ss}] {msg}");
                StatusMessage = msg;
            });
            
            var results = await _filterService.FilterStocksAsync(
                FilterOptions, progress, _cancellationTokenSource.Token);
            
            // 更新筛选结果
            foreach (var score in results)
            {
                FilteredStocks.Add(new StockViewModel
                {
                    Rank = score.Rank,
                    StockCode = score.StockCode,
                    StockName = score.IsPortfolioStock ? $"★{score.StockName}" : score.StockName,
                    StrengthScore = score.StrengthScore,
                    StrengthLabel = score.StrengthLabel,
                    IsPortfolioStock = score.IsPortfolioStock,
                    SuperTrendScore = score.SuperTrendScore,
                    VegasScore = score.VegasScore,
                    BollingerScore = score.BollingerScore,
                    OccScore = score.OccScore,
                    SlopeScore = score.SlopeScore
                });
            }
            
            FilteredStockCount = FilteredStocks.Count;
            StatusMessage = $"筛选完成，共 {FilteredStockCount} 只股票";
        }
        catch (OperationCanceledException)
        {
            StatusMessage = "筛选已取消";
        }
        catch (Exception ex)
        {
            LogMessages.Add($"筛选失败: {ex.Message}");
            StatusMessage = "筛选失败";
        }
        finally
        {
            IsBusy = false;
            _cancellationTokenSource?.Dispose();
            _cancellationTokenSource = null;
        }
    }

    [RelayCommand]
    private async Task ExportToCsvAsync()
    {
        try
        {
            if (!FilteredStocks.Any())
            {
                StatusMessage = "没有可导出的数据";
                return;
            }
            
            var scores = FilteredStocks.Select(s => new TrendScore
            {
                Rank = s.Rank,
                StockCode = s.StockCode,
                StockName = s.StockName?.Replace("★", "") ?? "",
                StrengthScore = s.StrengthScore,
                SuperTrendScore = s.SuperTrendScore,
                VegasScore = s.VegasScore,
                BollingerScore = s.BollingerScore,
                OccScore = s.OccScore,
                SlopeScore = s.SlopeScore,
                IsPortfolioStock = s.IsPortfolioStock
            });
            
            var filePath = await _csvExportService.ExportToCsvAsync(scores, FilterOptions.Date);
            StatusMessage = $"已导出到: {filePath}";
            LogMessages.Add($"CSV 已导出: {filePath}");
        }
        catch (Exception ex)
        {
            LogMessages.Add($"导出 CSV 失败: {ex.Message}");
            StatusMessage = "导出 CSV 失败";
        }
    }

    [RelayCommand]
    private void CancelOperation()
    {
        _cancellationTokenSource?.Cancel();
        StatusMessage = "正在取消...";
    }

    [RelayCommand]
    private void ClearLog()
    {
        LogMessages.Clear();
    }

    #endregion
}

/// <summary>
/// 股票 ViewModel
/// </summary>
public class StockViewModel
{
    public int Rank { get; set; }
    public string StockCode { get; set; } = string.Empty;
    public string StockName { get; set; } = string.Empty;
    public decimal StrengthScore { get; set; }
    public string StrengthLabel { get; set; } = string.Empty;
    public bool IsPortfolioStock { get; set; }
    public decimal SuperTrendScore { get; set; }
    public decimal VegasScore { get; set; }
    public decimal BollingerScore { get; set; }
    public decimal OccScore { get; set; }
    public decimal SlopeScore { get; set; }
}
