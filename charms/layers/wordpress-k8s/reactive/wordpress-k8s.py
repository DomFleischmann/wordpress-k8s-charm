from charms.layer.caas_base import pod_spec_set
from charms.reactive import endpoint_from_flag
from charms.reactive import when, when_not
from charms.reactive.flags import set_flag, clear_flag
from charmhelpers.core.hookenv import (
    log,
    metadata,
    config,
)
from charms import layer


@when_not('layer.docker-resource.wordpress-image.fetched')
def fetch_image():
    """Fetch the wordpress-image

    Conditions:
        - Not wordpress-image.fetched
    """
    layer.docker_resource.fetch('wordpress-image')


@when('layer.docker-resource.wordpress-image.failed')
def waiting_for_wordpress_image():
    """Set status blocked

    Conditions:
        - wordpress-image.failed
    """
    layer.status.blocked('Unable to fetch wordpress-image')


@when('layer.docker-resource.wordpress-image.available')
@when('wordpressdb.available')
@when_not('wordpress-k8s.configured')
def configure():
    """Configure wordpress-k8s pod

    Conditions:
        - wordpress-image.available
        - Not wordpress-k8s.configured
    """
    layer.status.maintenance('Configuring wordpress container')
    try:
        wordpressdb = endpoint_from_flag('wordpressdb.available')

        spec = make_pod_spec(
            wordpressdb.host(), 
            wordpressdb.user(), 
            wordpressdb.password(), 
        )

        log('set pod spec: {}'.format(spec))
        success = pod_spec_set(spec)
        if success:
            set_flag('wordpress-k8s.configured')
            layer.status.active('configured')
        else:
            layer.status.blocked('k8s spec failed to deploy')

    except Exception as e:
        layer.status.blocked('k8s spec failed to deploy: {}'.format(e))


@when('wordpress-k8s.configured')
def set_wordpress_active():
    """Set wordpress status active

    Conditions:
        - wordpress-k8s.configured
    """
    layer.status.active('configured')


def make_pod_spec(wp_db_host, wp_db_user, wp_db_password):
    """Make pod specification for Kubernetes

    Returns:
        pod_spec: Pod specification for Kubernetes
    """
    image_info = layer.docker_resource.get_info('wordpress-image')

    with open('reactive/spec_template.yaml') as spec_file:
        pod_spec_template = spec_file.read()

    md = metadata()
    cfg = config()

    data = {
        'name': md.get('name'),
        'docker_image_path': image_info.registry_path,
        'docker_image_username': image_info.username,
        'docker_image_password': image_info.password,
        'wordpress_db_host': wp_db_host,
        'wordpress_db_user': wp_db_user,
        'wordpress_db_password': wp_db_password,
    }
    data.update(cfg)
    return pod_spec_template % data


def get_wordpress_port():
    """Returns wordpress port"""
    cfg = config()
    return cfg.get('advertised-port')

