using System.Collections;
using System.Globalization;
using System.Windows.Data;

namespace TradingList.WPF.Converters;

/// <summary>
/// 集合转字符串转换器
/// </summary>
public class CollectionToStringConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is IEnumerable collection)
        {
            return string.Join(Environment.NewLine, collection.OfType<object>().Select(x => x?.ToString() ?? ""));
        }
        return string.Empty;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}
