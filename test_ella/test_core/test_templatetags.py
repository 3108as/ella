# -*- coding: utf-8 -*-
from unittest import TestCase as UnitTestCase
from django.test import TestCase

from nose import tools

from django import template
from django.template import TemplateSyntaxError
from django.contrib.sites.models import Site

from ella.core.templatetags.core import listing_parse, ListingNode, _parse_box, BoxNode, EmptyNode
from ella.core.models import Listing, Category
from ella.articles.models import Article
from ella.photos.models import Photo

from test_ella.test_core import create_basic_categories, create_and_place_a_publishable, \
        create_and_place_more_publishables, list_all_publishables_in_category_by_hour, \
        create_and_place_two_publishables_and_listings
from test_ella import template_loader

class TestRenderTag(UnitTestCase):
    def test_raises_error_on_no_args(self):
        t = '{% render %}'
        tools.assert_raises(template.TemplateSyntaxError, template.Template, t)

    def test_raises_error_on_more_args(self):
        t = '{% render 1 2 3 %}'
        tools.assert_raises(template.TemplateSyntaxError, template.Template, t)

    def test_fail_silently_on_empty_var(self):
        t = template.Template('{% render var_name %}')
        tools.assert_equals('', t.render(template.Context()))

    def test_renders_var(self):
        t = template.Template('{% render var %}')
        tools.assert_equals('XXX', t.render(template.Context({'var': 'XXX'})))

    def test_renders_nested_var(self):
        t = template.Template('{% render var.subvar.subsubvar %}')
        var = {'subvar': {'subsubvar': 'XXX'}}
        tools.assert_equals('XXX', t.render(template.Context({'var': var})))

    def test_renders_var_in_context(self):
        t = template.Template('{% render var %}')
        tools.assert_equals('YYY', t.render(template.Context({'var': '{{ other_var }}', 'other_var' : 'YYY'})))

    def test_does_not_escape_output(self):
        t = template.Template('{% render var %}')
        tools.assert_equals('<html> ""', t.render(template.Context({'var': '<html> ""'})))

class TestListingTag(TestCase):
    def setUp(self):
        super(TestListingTag, self).setUp()
        create_basic_categories(self)
        create_and_place_a_publishable(self)
        create_and_place_more_publishables(self)
        list_all_publishables_in_category_by_hour(self)

    def test_get_listing(self):
        t = template.Template('{% listing 10 for category as var %}{{ var|join:":" }}')
        expected = ':'.join([str(listing) for listing in self.listings if listing.category == self.category])
        tools.assert_equals(expected, t.render(template.Context({'category': self.category})))

    def test_get_listing_with_immediate_children(self):
        t = template.Template('{% listing 10 for category with children as var %}{{ var|join:":" }}')
        expected = ':'.join([str(listing) for listing in self.listings if listing.category in (self.category, self.category_nested)])
        tools.assert_equals(expected, t.render(template.Context({'category': self.category})))

    def test_get_listing_with_immediate_children_and_offset(self):
        t = template.Template('{% listing 10 from 2 for category with children as var %}{{ var|join:":" }}')
        expected = ':'.join([str(listing) for listing in self.listings if listing.category in (self.category, self.category_nested)][1:])
        tools.assert_equals(expected, t.render(template.Context({'category': self.category})))

    def test_get_listing_with_immediate_children_offset_and_count(self):
        t = template.Template('{% listing 1 from 2 for category with children as var %}{{ var|join:":" }}')
        expected = [str(listing) for listing in self.listings if listing.category in (self.category, self.category_nested)][1]
        tools.assert_equals(expected, t.render(template.Context({'category': self.category})))

class TestListingTagParser(UnitTestCase):
    '''
    {% listing <limit>[ from <offset>][of <app.model>[, <app.model>[, ...]]][ for <category> ] [with children|descendents] as <result> %}
    '''

    def test_minimal_args(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'as', 'var'])
        tools.assert_equals('var', var_name)
        tools.assert_equals({'count': '1'}, parameters)
        tools.assert_equals(['count'], parameters_to_resolve)

    def test_offset(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'from', '10', 'as', 'var'])
        tools.assert_true('offset' in parameters_to_resolve)
        tools.assert_equals('10', parameters['offset'])

    def test_limit_by_model(self):
        from ella.articles.models import Article
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'of', 'articles.article', 'as', 'var'])
        tools.assert_equals('var', var_name)
        tools.assert_equals('1', parameters['count'])
        tools.assert_equals([Article], parameters['mods'])

    def test_limit_bu_more_models(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'of', 'articles.article,photos.photo', 'as', 'var'])
        tools.assert_equals([Article, Photo], parameters['mods'])

    def test_limit_bu_more_models_space(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'of', 'articles.article,', 'photos.photo', 'as', 'var'])
        tools.assert_equals([Article, Photo], parameters['mods'])

    def test_limit_bu_more_models_space_around_comma(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'of', 'articles.article', ',', 'photos.photo', 'as', 'var'])
        tools.assert_equals([Article, Photo], parameters['mods'])

    def test_limit_by_category(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'for', 'category', 'as', 'var'])
        tools.assert_equals('category', parameters['category'])
        tools.assert_equals(['count', 'category'], parameters_to_resolve)

    def test_limit_by_category_with_descendents(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'for', 'category', 'with', 'descendents', 'as', 'var'])
        tools.assert_equals('category', parameters['category'])
        tools.assert_equals(['count', 'category'], parameters_to_resolve)
        tools.assert_equals(Listing.objects.ALL, parameters['children'])

    def test_limit_by_category_with_children(self):
        var_name, parameters, parameters_to_resolve = listing_parse(['listing', '1', 'for', 'category', 'with', 'children', 'as', 'var'])
        tools.assert_equals('category', parameters['category'])
        tools.assert_equals(['count', 'category'], parameters_to_resolve)
        tools.assert_equals(Listing.objects.IMMEDIATE, parameters['children'])

class TestBoxTag(UnitTestCase):

    def tearDown(self):
        super(TestBoxTag, self).tearDown()
        template_loader.templates = {}

    def test_renders_correct_template(self):
        template_loader.templates['box/box.html'] = '{{ object }}'
        t = template.Template('{% box name for sites.site with pk 1 %}{% endbox %}')
        tools.assert_equals('example.com', t.render(template.Context()))

    def test_params_are_parsed(self):
        template_loader.templates['box/box.html'] = '{% for k,v in box.params.items %}{{k}}:{{v}}|{% endfor %}'
        t = template.Template('''{% box name for sites.site with pk 1 %}
                level: 2
                some_other_param: xxx
            {% endbox %}''')
        tools.assert_equals('some_other_param:xxx|level:2|', t.render(template.Context()))

    def test_box_wirks_with_variable_instead_of_lookup(self):
        site = Site.objects.get(pk=1)
        template_loader.templates['box/box.html'] = '{{ object }}'
        t = template.Template('{% box name for var %}{% endbox %}')
        tools.assert_equals('example.com', t.render(template.Context({'var': site})))

    def test_box_for_empty_object_renders_empty(self):
        template_loader.templates['box/box.html'] = 'XXX'
        t = template.Template('{% box name for var %}{% endbox %}')
        tools.assert_equals('', t.render(template.Context({'var': None})))

class TestBoxTagParser(UnitTestCase):
    def test_parse_box_with_pk(self):
        node = _parse_box([], ['box', 'box_type', 'for', 'core.category', 'with', 'pk', '1'])
        tools.assert_true(isinstance(node, BoxNode))
        tools.assert_equals('box_type', node.box_type)
        tools.assert_equals(Category, node.model)
        tools.assert_equals(('pk', '1'), node.lookup)

    def test_parse_box_for_varname(self):
        node = _parse_box([], ['box', 'other_box_type', 'for', 'var_name'])
        tools.assert_true(isinstance(node, BoxNode))
        tools.assert_equals('other_box_type', node.box_type)
        tools.assert_equals('var_name', node.var_name)

    def test_parse_box_with_slug(self):
        node = _parse_box([], ['box', 'box_type', 'for', 'sites.site', 'with', 'slug', '"home"'])
        tools.assert_true(isinstance(node, BoxNode))
        tools.assert_equals('box_type', node.box_type)
        tools.assert_equals(Site, node.model)
        tools.assert_equals(('slug', '"home"'), node.lookup)

    def test_parse_raises_on_too_many_arguments(self):
        tools.assert_raises(TemplateSyntaxError, _parse_box, [], ['box', 'box_type', 'for', 'core.category', 'with', 'pk', '1', '2', 'extra'])

    def test_parse_raises_on_too_few_arguments(self):
        tools.assert_raises(TemplateSyntaxError, _parse_box, [], ['box', 'box_type', 'for'])

    def test_parse_raises_on_incorrect_arguments(self):
        tools.assert_raises(TemplateSyntaxError, _parse_box, [], ['box', 'box_type', 'not a for', 'core.category', 'with', 'pk', '1'])

    def test_parse_return_empty_node_on_incorrect_model(self):
        node = _parse_box([], ['box', 'box_type', 'for', 'not_app.not_model', 'with', 'pk', '1'])
        tools.assert_true(isinstance(node, EmptyNode))

