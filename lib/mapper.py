"""
    Mapper
"""
from internal.tools import to_m2m, to_m2o
from internal.exceptions import SkippingException
import base64
import os


def const(value):
    def const_fun(line):
        return value
    return const_fun

def val(field, default='', postprocess=lambda x: x, skip=False):
    def val_fun(line):
        if not line[field] and skip:
            raise SkippingException("Missing Value for %s" % field)
        return postprocess(line.get(field, default) or default)
    return val_fun

def val_fallback(field, fallback_file, default='', postprocess=lambda x: x, skip=False):
    def val_fun(line):
        if not line[field] and not line[fallback_file] and skip:
            raise SkippingException("Missing Value for %s" % field)
        value = line[field] or line[fallback_file] or default
        return postprocess(value)
    return val_fun

def val_label(field, default='', postprocess=lambda x: x, skip=False):
    val_m = val(field, default=default, postprocess=postprocess, skip=skip)
    def val_label_fun(line):
        return "%s : %s" % (field, val_m(line))
    return val_label_fun

def concat_mapper(separtor, *mapper):
    def concat_fun(line):
        return separtor.join([m(line) for m in mapper if m(line)])
    return concat_fun

def concat(separtor, *fields):
    return concat_mapper(separtor, *[val(f) for f in fields])

def concat_field(separtor, *fields):
    return concat_mapper(separtor, *[val_label(f) for f in fields])

def map_val(field, mapping, default=''):
    return val(field, postprocess=lambda x : mapping.get(x, default))

def num(field, default='0.0'):
    return val(field, default, postprocess=lambda x: x.replace(',', '.'))

def m2o(PREFIX, field, default='', skip=False):
    def m2o_fun(line):
        if skip and not line[field]:
            raise SkippingException("Missing Value for %s" % field)
        return to_m2o(PREFIX, line[field], default=default)
    return m2o_fun

def m2m(PREFIX, *args):
    """
        @param args: list of string that should be included into the m2m field
    """
    #TODO: add default
    def m2m_fun(line):
        return ','.join([to_m2m(PREFIX, line[f]) for f in args if line[f]])
    return m2m_fun



def bool_val(field, true_vals=[], false_vals=[]):
    def bool_val_fun(line):
        if line[field] in true_vals:
            return '1'
        if line[field] in false_vals:
            return '0'
        return '1' if line[field] else '0'
    return bool_val_fun

def binary(field, path_prefix, skip=False):
    def binary_val(line):
        path = path_prefix + (line[field] or '')
        if not os.path.exists(path):
            if skip:
                raise SkippingException("Missing File %s for field %s" % (path, field))
            return ''

        with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read())
                image_file.close()
        return encoded_string
    return binary_val

"""
    Specific to attribute mapper

"""

def val_att(att_list):
    def val_att_fun(line):
        return { att : line[att] for att in att_list if line[att]}
    return val_att_fun

def m2o_att(PREFIX, att_list):
    def m2o_att_fun(line):
        return { att : to_m2o(PREFIX, line[att]) for att in att_list if line[att]}
    return m2o_att_fun

def m2o_att_name(PREFIX, att_list):
    def m2o_att_fun(line):
        return { att : to_m2o(PREFIX, att) for att in att_list if line[att]}
    return m2o_att_fun


"""
    Mapper that require rpc Connection (conf_lib)
"""
def database_id_mapper(PREFIX, field, connection, skip=False):
    def database_id_mapper_fun(line):
        res = to_m2o(PREFIX, line[field])
        if res:
            module, name = res.split('.')
            rec = connection.get_model('ir.model.data').search_read([('module', '=', module), ('name', '=', name)], ['res_id'])
            if rec and rec[0]['res_id']:
                return str(rec[0]['res_id'])
        if skip:
            raise SkippingException("%s not found" % res)
        return ''
    return database_id_mapper_fun

def database_id_mapper_fallback(connection, *fields_mapper, **kwargs):
    skip = kwargs.get("skip")
    def database_id_mapper_fun(line):
        res = [f(line) for f in fields_mapper if f(line)]
        if res:
            res = res[0]
            module, name = res.split('.')
            rec = connection.get_model('ir.model.data').search_read([('module', '=', module), ('name', '=', name)], ['res_id'])
            if rec and rec[0]['res_id']:
                return str(rec[0]['res_id'])
        if skip:
            raise SkippingException("%s not found" % res)
        return ''
    return database_id_mapper_fun

def database_id_mapper_fallback_create(connection, model, *fields_mapper, **kwargs):
    skip = kwargs.get("skip")
    def database_id_mapper_fun(line):
        res = [f(line) for f in fields_mapper if f(line)]
        if res:
            res = res[0]
            module, name = res.split('.')
            rec = connection.get_model('ir.model.data').search_read([('module', '=', module), ('name', '=', name)], ['res_id'])
            if rec and rec[0]['res_id']:
                return str(rec[0]['res_id'])
            else:
                print "import"
                connection.get_model(model).load(['id', 'name'], [[res, res]], context={'tracking_disable' : True, 'create_product_variant' : True,})
                return database_id_mapper_fun(line)
        if skip:
            raise SkippingException("%s not found" % res)
        return ''
    return database_id_mapper_fun



#For many2many specific process
def m2m_id_list(PREFIX, *args, **kwargs):
    """
        @param args: list of string that should be included into the m2m field
        @param const_values: constant values that will be add to all line
    """
    const_values = kwargs.get("const_values", [])
    def split_m2m_id_fun(line):
        """ Return a list of unique element (xml_id, name)
        """
        value = ','.join([to_m2m(PREFIX, line[f]) for f in args if line[f]] + const_values)
        s = []
        for val in value.split(','):
            if val.strip():
                s.append(val)
        return s
    return split_m2m_id_fun

def m2m_value_list(*args, **kwargs):
    """
        @param args: list of string that should be included into the m2m field
        @param const_values: constant values that will be add to all line
    """
    const_values = kwargs.get("const_values", [])
    def split_m2m_value_fun(line):
        """ Return a list of unique element (xml_id, name)
        """
        value = ','.join([line[f] for f in args if line[f]] + const_values)
        s = []
        for val in value.split(','):
            if val.strip():
                s.append(val)
        return s
    return split_m2m_value_fun


##############################
#                            #
#        Split Mapper        #
#                            #
##############################

def split_line_number(line_nb):
    """
        Return a function that can we used by split method from Processor class,
        this function will split the data every x lines where x is given by the param line_nb
        :param line_nb: 
    """
    def split(line, i):
        return divmod(i, line_nb)[0]
    return split