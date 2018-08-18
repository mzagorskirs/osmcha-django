# Generated by Django 2.0.3 on 2018-04-25 13:11

from django.db import migrations


def filtered_json(feature):
    PRIMARY_TAGS = [
        'aerialway',
        'aeroway',
        'amenity',
        'barrier',
        'boundary',
        'building',
        'craft',
        'emergency',
        'geological',
        'highway',
        'historic',
        'landuse',
        'leisure',
        'man_made',
        'military',
        'natural',
        'office',
        'place',
        'power',
        'public_transport',
        'railway',
        'route',
        'shop',
        'tourism',
        'waterway'
    ]
    data = {
        "osm_id": feature.osm_id,
        "url": "{}-{}".format(feature.osm_type, feature.osm_id),
        "version": feature.osm_version,
        "reasons": [reason.id for reason in feature.reasons.all()]
    }
    try:
        data['name'] = feature.geojson['properties']['name']
        tags = feature.geojson['properties']
        [
            tags.pop(key)
            for key in list(tags.keys())
            if key not in PRIMARY_TAGS
        ]
        data['primary_tags'] = tags
    except KeyError:
        pass
    return data


def migrate_features(apps, schema_editor):
    Changeset = apps.get_model('changeset', 'Changeset')
    for changeset in Changeset.objects.filter(features__isnull=False):
        new_features_data = [
            filtered_json(feature) for feature in changeset.features.all()
            ]
        changeset.new_features = new_features_data
        changeset.save(update_fields=['new_features'])


class Migration(migrations.Migration):

    dependencies = [
        ('changeset', '0050_changeset_new_features'),
        ('feature', '0016_auto_20180307_1417')
    ]

    operations = [
        migrations.RunPython(
            migrate_features, reverse_code=migrations.RunPython.noop
        ),
    ]