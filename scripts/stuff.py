import genmsg.msgs

MSG_TYPE_TO_CPP = {'byte': 'int8_t',
                   'char': 'uint8_t',
                   'bool': 'uint8_t',
                   'uint8': 'uint8_t',
                   'int8': 'int8_t', 
                   'uint16': 'uint16_t',
                   'int16': 'int16_t', 
                   'uint32': 'uint32_t',
                   'int32': 'int32_t',
                   'uint64': 'uint64_t',
                    'int64': 'int64_t',
                   'float32': 'float',
                   'float64': 'double',
                   'string': 'std::basic_string<char, std::char_traits<char>, typename ContainerAllocator::template rebind<char>::other > ',
                   'time': 'ros::Time',
                   'duration': 'ros::Duration'}

def msg_type_to_cpp(type):
    """
    Converts a message type (e.g. uint32, std_msgs/String, etc.) into the C++ declaration
    for that type (e.g. uint32_t, std_msgs::String_<ContainerAllocator>)
    
    @param type: The message type
    @type type: str
    @return: The C++ declaration
    @rtype: str
    """
    (base_type, is_array, array_len) = genmsg.msgs.parse_type(type)
    cpp_type = None
    if (genmsg.msgs.is_builtin(base_type)):
        cpp_type = MSG_TYPE_TO_CPP[base_type]
    elif (len(base_type.split('/')) == 1):
        if (genmsg.msgs.is_header_type(base_type)):
            cpp_type = ' ::std_msgs::Header_<ContainerAllocator> '
        else:
            cpp_type = '%s_<ContainerAllocator> '%(base_type)
    else:
        pkg = base_type.split('/')[0]
        msg = base_type.split('/')[1]
        cpp_type = ' ::%s::%s_<ContainerAllocator> '%(pkg, msg)
        
    if (is_array):
        if (array_len is None):
            return 'std::vector<%s, typename ContainerAllocator::template rebind<%s>::other > '%(cpp_type, cpp_type)
        else:
            return 'boost::array<%s, %s> '%(cpp_type, array_len)
    else:
        return cpp_type

def cpp_message_declarations(name_prefix, msg):
    """
    Returns the different possible C++ declarations for a message given the message itself.
    
    @param name_prefix: The C++ prefix to be prepended to the name, e.g. "std_msgs::"
    @type name_prefix: str
    @param msg: The message type
    @type msg: str
    @return: A tuple of 3 different names.  cpp_message_decelarations("std_msgs::", "String") returns the tuple
        ("std_msgs::String_", "std_msgs::String_<ContainerAllocator>", "std_msgs::String")
    @rtype: str 
    """
    pkg, basetype = genmsg.names.package_resource_name(msg)
    cpp_name = ' ::%s%s'%(name_prefix, msg)
    if (pkg):
        cpp_name = ' ::%s::%s'%(pkg, basetype)
    return ('%s_'%(cpp_name), '%s_<ContainerAllocator> '%(cpp_name), '%s'%(cpp_name))

def escape_string(str):
    str = str.replace('\\', '\\\\')
    str = str.replace('"', '\\"')
    return str
        
def is_fixed_length(spec, includepath):
    """
    Returns whether or not the message is fixed-length
    
    @param spec: The message spec
    @type spec: genmsg.msgs.MsgSpec
    @param package: The package of the
    @type package: str
    """
    assert isinstance(includepath, list)
    types = []
    for field in spec.parsed_fields():
        if (field.is_array and field.array_len is None):
            return False
        
        if (field.base_type == 'string'):
            return False
        
        if (not field.is_builtin):
            types.append(field.base_type)
            
    types = set(types)
    for type in types:
        type = genmsg.msgs.resolve_type(type, spec.package)
        (_, new_spec) = genmsg.msg_loader.load_msg_by_type(msg_context, type, includepath, spec.package)
        if (not is_fixed_length(new_spec, includepath)):
            return False
        
    return True
    
def compute_full_text_escaped(gen_deps_dict):
    """
    Same as genmsg.gentools.compute_full_text, except that the
    resulting text is escaped to be safe for C++ double quotes

    @param get_deps_dict: dictionary returned by get_dependencies call
    @type  get_deps_dict: dict
    @return: concatenated text for msg/srv file and embedded msg/srv types. Text will be escaped for double quotes
    @rtype: str
    """
    definition = genmsg.gentools.compute_full_text(gen_deps_dict)
    lines = definition.split('\n')
    s = StringIO()
    for line in lines:
        line = escape_string(line)
        s.write('%s\\n\\\n'%(line))
        
    val = s.getvalue()
    s.close()
    return val

def default_value(type):
    """
    Returns the value to initialize a message member with.  0 for integer types, 0.0 for floating point, false for bool,
    empty string for everything else
    
    @param type: The type
    @type type: str
    """
    if type in ['byte', 'int8', 'int16', 'int32', 'int64',
                'char', 'uint8', 'uint16', 'uint32', 'uint64']:
        return '0'
    elif type in ['float32', 'float64']:
        return '0.0'
    elif type == 'bool':
        return 'false'

    return ""

def takes_allocator(type):
    """
    Returns whether or not a type can take an allocator in its constructor.  False for all builtin types except string.
    True for all others.
    
    @param type: The type
    @type: str
    """
    return not type in ['byte', 'int8', 'int16', 'int32', 'int64',
                        'char', 'uint8', 'uint16', 'uint32', 'uint64',
                        'float32', 'float64', 'bool', 'time', 'duration']

def generate_fixed_length_assigns(spec, container_gets_allocator, cpp_name_prefix):
    """
    Initialize any fixed-length arrays
    
    @param s: The stream to write to
    @type s: stream
    @param spec: The message spec
    @type spec: genmsg.msgs.MsgSpec
    @param container_gets_allocator: Whether or not a container type (whether it's another message, a vector, array or string)
        should have the allocator passed to its constructor.  Assumes the allocator is named _alloc.
    @type container_gets_allocator: bool
    @param cpp_name_prefix: The C++ prefix to use when referring to the message, e.g. "std_msgs::"
    @type cpp_name_prefix: str
    """
    # Assign all fixed-length arrays their default values
    for field in spec.parsed_fields():
        if (not field.is_array or field.array_len is None):
            continue

        val = default_value(field.base_type)
        if (container_gets_allocator and takes_allocator(field.base_type)):
            # String is a special case, as it is the only builtin type that takes an allocator
            if (field.base_type == "string"):
                string_cpp = msg_type_to_cpp("string")
                yield '    %s.assign(%s(_alloc));\n'%(field.name, string_cpp)
            else:
                (cpp_msg_unqualified, cpp_msg_with_alloc, _) = cpp_message_declarations(cpp_name_prefix, field.base_type)
                yield '    %s.assign(%s(_alloc));\n'%(field.name, cpp_msg_with_alloc)
        elif (len(val) > 0):
            yield '    %s.assign(%s);\n'%(field.name, val)


def generate_initializer_list(spec, container_gets_allocator):
    """
    Writes the initializer list for a constructor
    
    @param s: The stream to write to
    @type s: stream
    @param spec: The message spec
    @type spec: genmsg.msgs.MsgSpec
    @param container_gets_allocator: Whether or not a container type (whether it's another message, a vector, array or string)
        should have the allocator passed to its constructor.  Assumes the allocator is named _alloc.
    @type container_gets_allocator: bool
    """

    op = ':'
    for field in spec.parsed_fields():
        val = default_value(field.base_type)
        use_alloc = takes_allocator(field.base_type)
        if (field.is_array):
            if (field.array_len is None and container_gets_allocator):
                yield '  %s %s(_alloc)'%(op, field.name)
            else:
                yield '  %s %s()'%(op, field.name)
        else:
            if (container_gets_allocator and use_alloc):
                yield '  %s %s(_alloc)'%(op, field.name)
            else:
                yield '  %s %s(%s)'%(op, field.name, val)
        op = ','
