import click
import click_logging
import logging
import os
import yaml
from jinja2 import Environment, FileSystemLoader
import packer_cli.templates.templates as templates


logger = logging.getLogger(__name__)
click_logging.basic_config(logger)


@click.group()
@click_logging.simple_verbosity_option(logger)
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@click.pass_context
@click_logging.simple_verbosity_option(logger)
@click.option("--path", help="Path (full or relative) to initialise into")
def init(ctx, path):

    dirs = ["/jinja", "/packer/ansible/base", "/packer/scripts"]

    try:
        logger.info("Creating directory structure...")
        if not os.path.exists(path):
            os.mkdir(path)

        for dir in dirs:
            if not os.path.exists(path + dir):
                os.makedirs(path + dir)

    except Exception as e:
        logger.error(e)
    try:
        logger.info("Creating templates... ")
        try:
            for file in templates.files:
                f = open(path + file["location"], "w")
                f.write(file["content"])
                f.close
        except Exception as e:
            logger.error(e)
    except Exception as e:
        logger.error(e)


@cli.command()
@click.pass_context
@click_logging.simple_verbosity_option(logger)
@click.option("--path", help="Path (full or relative) for project")
def render(ctx, path):
    logger.debug("Loading YAML Config")
    with open(path + "/config.yaml", "r") as file:
        yml_config = yaml.safe_load(file)

    template_path = path + "/jinja"
    packer_path = path + "/packer"

    logger.debug("Loading Jinja2 templates for rendering")
    templates = os.listdir(template_path)
    environment = Environment(loader=FileSystemLoader(searchpath=template_path))

    for file in templates:
        filename = packer_path + "/" + file.rsplit(".")[0] + ".pkr.hcl"
        template = environment.get_template(file)
        logger.debug("Rendering file: " + file)
        with open(filename, "w") as f:
            f.write(template.render(yml_config))
            f.close()
