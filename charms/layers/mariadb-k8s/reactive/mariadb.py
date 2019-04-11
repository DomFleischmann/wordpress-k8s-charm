from charms.reactive import when, when_not
from charms.reactive import endpoint_from_flag
from charms.reactive.flags import set_flag, get_state, is_flag_set, clear_flag, get_flags

from charmhelpers.core.hookenv import (
    log,
    metadata,
    status_set,
    config,
    network_get,
    relation_id,
)
from charms import layer


@when_not('layer.docker-resource.mysql-image.fetched')
def fetch_image():
    layer.docker_resource.fetch('mysql-image')


@when('mysql.configured')
def mariadb_active():
    status_set('active', '')


@when('layer.docker-resource.mysql-image.available')
@when_not('mysql.configured')
def config_mariadb():
    status_set('maintenance', 'Configuring mysql container')

    spec = make_pod_spec()
    log('set pod spec:\n{}'.format(spec))
    layer.caas_base.pod_spec_set(spec)

    set_flag('mysql.configured')


def make_pod_spec():
    with open('reactive/spec_template.yaml') as spec_file:
        pod_spec_template = spec_file.read()

    md = metadata()
    cfg = config()

    user = cfg.get('user')
    set_flag('user', user)
    password = cfg.get('password')
    set_flag('password', password)
    database = cfg.get('database')
    set_flag('database', database)
    root_password = cfg.get('root_password')
    set_flag('root_password', root_password)

    image_info = layer.docker_resource.get_info('mysql-image')

    data = {
        'name': md.get('name'),
        'docker_image_path': image_info.registry_path,
        'docker_image_username': image_info.username,
        'docker_image_password': image_info.password,
        'port': cfg.get('mysql_port'),
        'user': user,
        'password': password,
        'database': database,
        'root_password': root_password,
    }
    data.update(cfg)
    return pod_spec_template % data


@when('mysql.configured', 'server.database.requested')
def provide_database():
    mysql = endpoint_from_flag('server.database.requested')
    if not is_pod_up('server'):
        log("The pod is not ready.")
        return

    log('db requested')
    # log('provide_database: all flags: {}'.format(get_flags()))

    for request, application in mysql.database_requests().items():
        try:
            # if is_flag_set(''):

            log('request -> {0} for app -> {1}'.format(request, application))
            database_name = get_state('database')
            user = get_state('user')
            password = get_state('password')

            log('db params: {0}:{1}@{2}'.format(user, password, database_name))
            # info = network_get('server', relation_id())
            # log('network info {0}'.format(info))

            service_ip = get_service_ip('server')
            if service_ip:
                mysql.provide_database(
                    request_id=request,
                    host=service_ip,
                    port=3306,
                    database_name=database_name,
                    user=user,
                    password=password,
                )
                mysql.mark_complete()

            # # Test: set a flag that we've provided this db
            # set_flag('db-{}-provided'.format(request))

        except Exception as e:
            log('Exception while providing database: {}'.format(e))

def is_pod_up(endpoint):
    info = network_get(endpoint, relation_id())

    # Check to see if the pod has been assigned it's internal and external ips
    for ingress in info['ingress-addresses']:
        if len(ingress) == 0:
            return False

    return True


def get_service_ip(endpoint):
    try:
        info = network_get(endpoint, relation_id())
        if 'ingress-addresses' in info:
            addr = info['ingress-addresses'][0]
            if len(addr):
                return addr
        else:
            log("No ingress-addresses: {}".format(info))
    except Exception as e:
        log("Caught exception checking for service IP: {}".format(e))

    return None
