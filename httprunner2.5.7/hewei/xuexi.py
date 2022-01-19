import ast


def parse_string_value(str_value):
    """ parse string to number if possible
        如果可能的话，将字符串解析为数字,列表，字典
    e.g. "123" => 123
         "12.2" => 12.3
         "abc" => "abc"
         "$var" => "$var"
    """
    print("调用函数：parse_string_value(str_value)")
    print("参数：{}".format(str_value))
    try:
        return ast.literal_eval(str_value)
    except ValueError:
        return str_value
    except SyntaxError:
        # e.g. $var, ${func}
        return str_value


str_value_01 = "123"
str_value_02 = "12.2"
str_value_03 = "abc"
str_value_04 = "$var"
str_value_05 = "${var($a, $b)}"
str_value_06 = "{a:1,b:2,c:3}"
a = parse_string_value(str_value_06)
print(a)
